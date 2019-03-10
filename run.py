import sys
import numpy
import dash
import pandas
from dash.dependencies import Input, Output
import dash_core_components as dcc
import dash_html_components as html
from pandas_datareader import data as web
from datetime import datetime as dt
from dateutil.relativedelta import relativedelta
import plotly
from plotly import tools
from plotly import figure_factory as FF
import urllib.parse

sys.path.append("lib")
import utils
import strategy
from loader import Loader
from simulator import Simulator, SimulatorSetting, SimulatorData

app = dash.Dash()

today = dt.now().strftime("%Y-%m-%d")
codes = Loader.realtime_sheet_stocks(today)

before = 3
date = utils.to_format(dt.now())
options = list(map(lambda x: {'label':x, 'value':x}, codes))

app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    html.Div([
        html.Div([
            dcc.Dropdown(id="strategy", options=[
                {"label": "combination", "value": "combination"},
                {"label": "daytrade", "value": "daytrade"},
                {"label": "falling", "value": "falling"},
                {"label": "rising", "value": "rising"},
                {"label": "nikkei", "value": "nikkei"},
                {"label": "new_high", "value": "new_high"},
            ], value="rising"),
            dcc.Dropdown(id="env", options=[
                {"label": "PRODUCTION", "value": "PRODUCTION"},
                {"label": "DEVELOP", "value": "DEVELOP"}
            ], value="PRODUCTION"),
            dcc.Dropdown(id="target", options=[
                {"label": "DAILY", "value": "DAILY"},
                {"label": "TICK", "value": "TICK"},
                {"label": "REALTIME", "value": "REALTIME"}
            ], value="DAILY"),
            dcc.Dropdown(id="method", options=[
                {"label": "SHORT", "value": "SHORT"},
                {"label": "LONG", "value": "LONG"},
            ], value="LONG"),
            dcc.Dropdown(id="code", options=options, value=""),
            dcc.Input(id="input_code", type="text", value="", placeholder="code"),
            dcc.Input(id="before", type="text", value=before, placeholder="term"),
            dcc.Input(id="date", type="text", value=date, placeholder="date"),
        ]),
    ]),
    dcc.Graph(id='stockchart', style={"height":1200}),
])

def add_stats(fig, row, col, data, df, keys, alpha=1.0, bar=False, mode="lines", size=1):
    for key in keys:
        if bar:
            data.append(plotly.graph_objs.Bar(x=df["date"], y=df[key], name=key))
        else:
            if mode == "lines":
                data.append(plotly.graph_objs.Scatter(x=df["date"], y=df[key], mode=mode, name=key, opacity=alpha, line={"width": size}))
            elif mode == "markers":
                data.append(plotly.graph_objs.Scatter(x=df["date"], y=df[key], mode=mode, name=key, opacity=alpha, marker={"size": size}))

    for d in data:
        fig.append_trace(d, row, col)
    return fig

def set_env(args, env):
    args.production = env == "PRODUCTION"
    return args

def set_target(args, target):
    args.realtime = target == "REALTIME"
    args.tick = target == "TICK" or args.realtime

    if args.tick:
        args.daytrade = True
    return args

def set_method(args, method):
    args.short = method == "SHORT"
    return args

def set_strategy(args, strategy_name):
    if strategy_name == "daytrade":
        args.daytrade = True
    elif strategy_name == "falling":
        args.falling = True
    elif strategy_name == "rising":
        args.rising = True
    elif strategy_name == "new_high":
        args.new_high = True

    return args

def create_args(url, env, target, code, input_code, method, strategy_name):

    parser = strategy.create_parser()
    args = parser.parse_args()

    args = set_env(args, env)
    args = set_target(args, target)
    args = set_method(args, method)
    args = set_strategy(args, strategy_name)

    args.code = code

    if len(input_code) > 0:
        args.code = input_code

    return args

def simulate(args, simulator_data, start, end):
    assets = Loader.assets()
    index = {}
    if not args.tick:
        for k in ["nikkei"]:
            data = Loader.load_index(k, start, end, with_filter=True, strict=False)
            index[k] = utils.add_index_stats(data)

    setting = SimulatorSetting()
    setting.strategy["daily"] = strategy.load_strategy(args)
    setting.assets = assets["assets"] if assets is not None else 1
    setting.short_trade = args.short
    setting.debug = True

    start_tick = "%s 15:00:00" % start
    end_tick = "%s 15:00:00" % end
    print(start_tick, end_tick)

    simulator = Simulator(setting)
    dates = simulator_data.dates(start_tick, end_tick)
    print(dates)
    stats = simulator.simulate(dates, simulator_data, index)

    simulator_data = simulator_data.split(start_tick, end_tick)
    return stats, simulator_data

@app.callback(Output("code", "options"), [Input("strategy", "value"), Input("target", "value")])
def update_codes(strategy_name, target):
    parser = strategy.create_parser()
    args = parser.parse_args()

    args = set_target(args, target)
    args = set_strategy(args, strategy_name)

    date = dt.now().strftime("%Y-%m-%d")

    strategy_creator = strategy.load_strategy_creator(args)
    codes = strategy_creator.subject(date)
    options = list(map(lambda x: {'label':x, 'value':x}, codes))
    return options

@app.callback(Output('stockchart', 'figure'), [Input('code', 'value'), Input("before", "value"), Input("date", "value"), Input("url", "href"), Input("input_code", "value"), Input("env", "value"), Input("target", "value"), Input("method", "value"), Input("strategy", "value")])
def update_stock_graph(code, before, date, url, input_code, env, target, method, strategy_name):

    args = create_args(url, env, target, code, input_code, method, strategy_name)

    end = date
    start = utils.to_format(utils.to_datetime(end) - utils.relativeterm(int(before), args.tick))

    simulator_data = strategy.load_simulator_data(args.code, start, end, args)
    stats, simulator_data = simulate(args, simulator_data, start, end)

    print(stats["trade_history"])
    print(stats["gain"])

    df = simulator_data.daily
    df = df[df["date"] >= start]
    df = df.reset_index()
    df["new"] = list(map(lambda x: x["new"], stats["trade_history"]))
    df["repay"] = list(map(lambda x: x["repay"], stats["trade_history"]))

    # 陽線-> candle.data[1], 陰線 -> candle.data[0]
    candle = FF.create_candlestick(df["open"], df["high"], df["low"], df["close"], dates=df["date"])
    stocks = list(candle.data)

    fig = tools.make_subplots(rows=9, cols=1, shared_xaxes=True, shared_yaxes=True)

    fig = add_stats(fig, 9, 1, [], df, ["new", "repay"], mode="markers", size=10)
    fig = add_stats(fig, 8, 1, [], df, ["volume"], bar=True)
    fig = add_stats(fig, 8, 1, [], df, ["volume_average"])
    fig = add_stats(fig, 7, 1, [], df, ["env_entity"], bar=True)
    fig = add_stats(fig, 7, 1, [], df, ["env_entity_average"])
    fig = add_stats(fig, 6, 1, [], df, ["atr"], bar=True)
    fig = add_stats(fig, 1, 1, [], df, ["rci", "rci_long"])
    fig = add_stats(fig, 2, 1, [], df, ["macd", "macdsignal"])
    fig = add_stats(fig, 2, 1, [], df, ["macdhist"], bar=True)
    fig = add_stats(fig, 3, 1, [], df, [
        "average_cross", "macd_cross", "rci_cross",
        "env12_cross", "env11_cross", "env09_cross", "env08_cross",
    ], bar=True)
    fig = add_stats(fig, 3, 1, [], df, ["stages", "stages_average"])
    fig = add_stats(fig, 4, 1, [], df, ["macd_trend", "macdhist_trend", "macdhist_convert", "rci_trend", "rci_long_trend"], bar=True)
    fig = add_stats(fig, 5, 1, [], df, ["daily_average_trend", "weekly_average_trend", "stages_trend", "stages_average_trend", "volume_average_trend"], bar=True)
    fig = add_stats(fig, 9, 1, [], df, ["env12", "env11", "env09", "env08"], alpha=0.3)
    fig = add_stats(fig, 9, 1, stocks, df, ["daily_average", "weekly_average"], alpha=0.9, size=3)
    fig = add_stats(fig, 9, 1, [], df, ["rising_safety", "fall_safety"], alpha=0.9, size=2)
    fig = add_stats(fig, 9, 1, [], df, ["resistance", "support"], alpha=0.6, size=2)

    fig.layout = plotly.graph_objs.Layout(
        xaxis=dict(
            type="category"
        ),
        yaxis=dict(
            domain=[0, 0.15],
        ),
        yaxis2=dict(
            domain=[0.15, 0.3]
        ),
        yaxis3=dict(
            domain=[0.3, 0.35]
        ),
        yaxis4=dict(
            domain=[0.35, 0.4]
        ),
        yaxis5=dict(
            domain=[0.4, 0.45]
        ),
        yaxis6=dict(
            domain=[0.45, 0.5]
        ),
        yaxis7=dict(
            domain=[0.5, 0.55]
        ),
        yaxis8=dict(
            domain=[0.55, 0.6]
        ),
        yaxis9=dict(
            domain=[0.6, 1.0]
        )

    )

    return fig

if __name__ == '__main__':
    app.run_server(host='0.0.0.0')
