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
import plotly.graph_objects as go
from plotly import subplots
from plotly import figure_factory as FF
import urllib.parse

sys.path.append("lib")
import utils
import strategy
from loader import Loader, Bitcoin
from simulator import Simulator, SimulatorSetting, SimulatorData

app = dash.Dash()

today = dt.now().strftime("%Y-%m-%d")
codes = []

before = 3
date = utils.to_format(dt.now())
options = list(map(lambda x: {'label':x, 'value':x}, codes))

app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    html.Div([
        html.Div([
            dcc.Dropdown(id="strategy", options=[
                {"label": "combination", "value": "combination"},
            ], value="combination"),
            dcc.Dropdown(id="env", options=[
                {"label": "PRODUCTION", "value": "PRODUCTION"},
                {"label": "DEVELOP", "value": "DEVELOP"}
            ], value="PRODUCTION"),
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

def set_method(args, method):
    args.short = method == "SHORT"
    return args

def create_args(url, env, code, input_code, method, strategy_name):

    parser = strategy.create_parser()
    args = parser.parse_args()

    args = set_env(args, env)
    args = set_method(args, method)

    args.code = code

    if len(input_code) > 0:
        args.code = input_code

    return args

def simulate(args, simulator_data, start, end):
    assets = Loader.assets()
    index = strategy.load_index(args, start, end)
    setting = strategy.create_simulator_setting(args)
    combination_setting = strategy.create_combination_setting(args)
    setting.strategy = strategy.load_strategy(args, combination_setting)
    setting.assets = assets["assets"] if assets is not None else 1
    setting.short_trade = args.short
    setting.debug = True

    start_time = "%s 15:00:00" % start
    end_time = "%s 15:00:00" % end

    if args.code in Bitcoin().exchanges:
        start_time = "%s 23:59:59" % start
        end_time = "%s 23:59:59" % end

    print(start_time, end_time)

    simulator = Simulator(setting)
    dates = simulator_data.dates(start_time, end_time)
    stats = simulator.simulate(dates, simulator_data, index)

    simulator_data = simulator_data.split(start_time, end_time)
    return stats, simulator_data

def set_strategy(args, strategy_name):
    return args

@app.callback(Output("code", "options"), [Input("strategy", "value"), Input("date", "value")])
def update_codes(strategy_name, date):
    parser = strategy.create_parser()
    args = parser.parse_args()

    args = set_strategy(args, strategy_name)

    combination_setting = strategy.create_combination_setting(args)
    strategy_creator = strategy.load_strategy_creator(args, combination_setting)
    codes = strategy_creator.subject(utils.to_format(utils.to_datetime(date) - utils.relativeterm(1)))
    options = list(map(lambda x: {'label':x, 'value':x}, codes))
    return options

@app.callback(Output('stockchart', 'figure'), [Input('code', 'value'), Input("before", "value"), Input("date", "value"), Input("url", "href"), Input("input_code", "value"), Input("env", "value"), Input("method", "value"), Input("strategy", "value")])
def update_stock_graph(code, before, date, url, input_code, env, method, strategy_name):

    args = create_args(url, env, code, input_code, method, strategy_name)

    end = date
    start = utils.to_format(utils.to_datetime(end) - utils.relativeterm(int(before)))

    simulator_data = strategy.load_simulator_data(args.code, start, end, args)
    stats, simulator_data = simulate(args, simulator_data, start, end)

    print(stats["trade_history"])
    print(stats["gain"])

    df = simulator_data.daily
    df = df[df["date"] >= start]
    df = df.reset_index()
    df["new"] = list(map(lambda x: x["new"], stats["trade_history"][:-1]))
    df["repay"] = list(map(lambda x: x["repay"], stats["trade_history"][:-1]))

    # 陽線-> candle.data[1], 陰線 -> candle.data[0]
    candle = FF.create_candlestick(df["open"], df["high"], df["low"], df["close"], dates=df["date"])
    stocks = list(candle.data)

    fig = subplots.make_subplots(rows=9, cols=1, shared_xaxes=True, shared_yaxes=True)

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
    fig = add_stats(fig, 4, 1, [], df, ["macd_trend", "macdhist_trend", "macdhist_convert", "rci_trend", "rci_long_trend", "rising_safety_trend", "fall_safety_trend"], bar=True)
    fig = add_stats(fig, 5, 1, [], df, ["daily_average_trend", "weekly_average_trend", "stages_trend", "stages_average_trend", "volume_average_trend"], bar=True)
    fig = add_stats(fig, 9, 1, [], df, ["env12", "env11", "env09", "env08"], alpha=0.3)
    fig = add_stats(fig, 9, 1, stocks, df, ["daily_average", "weekly_average"], alpha=0.9, size=3)
    fig = add_stats(fig, 9, 1, [], df, ["rising_safety", "fall_safety"], alpha=0.9, size=2)
    fig = add_stats(fig, 9, 1, [], df, ["resistance", "support"], alpha=0.6, size=2)


    rangebreaks = [dict(bounds=["sat", "mon"])]
    daterange = [df["date"].iloc[0], df["date"].iloc[-1]]

    fig.layout = plotly.graph_objs.Layout(
        xaxis=dict(range=daterange, rangebreaks=rangebreaks),
        xaxis2=dict(range=daterange, rangebreaks=rangebreaks),
        xaxis3=dict(range=daterange, rangebreaks=rangebreaks),
        xaxis4=dict(range=daterange, rangebreaks=rangebreaks),
        xaxis5=dict(range=daterange, rangebreaks=rangebreaks),
        xaxis6=dict(range=daterange, rangebreaks=rangebreaks),
        xaxis7=dict(range=daterange, rangebreaks=rangebreaks),
        xaxis8=dict(range=daterange, rangebreaks=rangebreaks),
        xaxis9=dict(range=daterange, rangebreaks=rangebreaks),
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
    date = dt.now().strftime("%Y-%m-%d")
    #update_codes("combination", date)
    app.run_server(host='0.0.0.0')
