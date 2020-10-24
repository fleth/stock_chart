import sys
import numpy
import json
import dash
import pandas
from dash.dependencies import Input, Output
import dash_core_components as dcc
import dash_html_components as html
import plotly
from plotly import tools
from plotly import figure_factory as FF

sys.path.append("lib")
import utils
from loader import Loader

app = dash.Dash()

options = [
    {"label": "日経平均", "value": "index/nikkei"},
]

app.layout = html.Div([
    dcc.Dropdown(id="target", options=[
        {"label": "futures", "value": "futures_"},
        {"label": "new_high_", "value": "new_high_"},
        {"label": "open_close_", "value": "open_close_"},
        {"label": "open_close_instant_", "value": "open_close_instant_"},
        {"label": "default_instant", "value": "instant_"},
        {"label": "default", "value": ""}
    ], value=""),
    dcc.Dropdown(id="env", options=[
        {"label": "PRODUCTION", "value": "production_"},
        {"label": "DEVELOP", "value": ""}
    ], value="production_"),
    dcc.Dropdown(id="method", options=[
        {"label": "long", "value": ""},
        {"label": "short", "value": "short_"}
    ], value=""),
    dcc.Graph(id='chart', style={"height":480}),
])


def load_performance(filename, path="simulate_settings/performances/"):
    f = open("%s%s" % (path, filename), "r")
    data = json.load(f)
    return data

@app.callback(Output('chart', 'figure'), [Input('target', 'value'), Input('env', 'value'), Input('method', 'value')])
def update_graph(target, env, method):

    setting = Loader.simulate_setting("%s%s%ssimulate_setting.json" % (env, target, method))
    performance = sorted(load_performance("%s%s%sperformance.json" % (env, target, method)).items(), key=lambda x: utils.to_datetime(x[0]))

    optimize_end_date = setting["date"]
    filterd_performance = list(filter(lambda x: utils.to_datetime(x[0]) < utils.to_datetime(optimize_end_date), performance))

    stats = {}
    stats["start_date"] = list(map(lambda x: x[1]["start_date"], filterd_performance))
    stats["gain"] = list(map(lambda x: x[1]["gain"], filterd_performance))
    stats["trade"] = list(map(lambda x: x[1]["trade"], filterd_performance))

    sum_gain = sum(stats["gain"]) # 総利益
    sum_trade = sum(stats["trade"]) # 総トレード数
    ave_trade = numpy.average(stats["trade"]).tolist() # 平均トレード数
    gain_per_trade = sum_gain / sum_trade # 1トレード当たりの利益

    report = {"gain":[], "average": []}
    report["date"] = list(map(lambda x: x[1]["start_date"], performance))
    gain = 0
    for i, x in enumerate(performance):
        gain = gain + x[1]["gain"]
        report["gain"] = report["gain"] + [gain]
        report["average"] = report["average"] + [i * ave_trade * gain_per_trade]

    df = pandas.DataFrame(report)

    fig = tools.make_subplots(rows=1, cols=1, shared_xaxes=True, shared_yaxes=True)
    fig.append_trace(plotly.graph_objs.Scatter(x=df["date"], y=df["gain"], mode="lines", name="gain"), 1, 1)
    fig.append_trace(plotly.graph_objs.Scatter(x=df["date"], y=df["average"], mode="lines", name="average"), 1, 1)
    return fig

if __name__ == '__main__':
    app.run_server(host='0.0.0.0', port=8052)

