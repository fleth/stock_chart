import sys
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

industry_code = Loader.industry_code().sort_values("industry_code")
options = [
    {"label": "日経平均", "value": "index/nikkei"},
    {"label": "ダウ平均", "value": "index/dow"},
    {"label": "ナスダック", "value": "index/nasdaq"},
    {"label": "TOPIX", "value": "index/topix"},
    {"label": "JASDAQ", "value": "index/jasdaq"},
    {"label": "円/ドル", "value": "index/usdjpy"},
    {"label": "ビットコイン", "value": "index/xbtusd"},
    {"label": "新高値新安値スコア", "value": "settings/new_score"},
    {"label": "新高値スコア", "value": "settings/new_high"},
    {"label": "新安値スコア", "value": "settings/new_low"},
]

for i, row in industry_code.iterrows():
    options = options + [
        {"label": row["name"], "value": "index/industry/%s" % row["industry_code"]}
    ]


app.layout = html.Div([
    dcc.Dropdown(id="filename", options=options, value="index/nikkei"),
    dcc.Dropdown(id="mode", options=[
        {"label": "lines", "value": "lines"},
        {"label": "bar", "value": "bar"},
        {"label": "markers", "value": "markers"}
    ], value="lines"),
    dcc.Input(id="x", type="text", value=0, placeholder="filename"),
    dcc.Input(id="y", type="text", value=1, placeholder="filename"),
    dcc.Graph(id='chart', style={"height":480}),
])

@app.callback(Output('chart', 'figure'), [Input('filename', 'value'), Input("x", "value"), Input("y", "value"), Input("mode", "value")])
def update_graph(filename, x, y, mode):
    print(filename, x, y)

    df = pandas.read_csv("%s/%s.csv" % (Loader.base_dir, filename))

    fig = tools.make_subplots(rows=1, cols=1, shared_xaxes=True, shared_yaxes=True)
    if mode == "bar":
        d = plotly.graph_objs.Bar(x=df.iloc[:,int(x)], y=df.iloc[:,int(y)], name=y)
    else:
        d = plotly.graph_objs.Scatter(x=df.iloc[:,int(x)], y=df.iloc[:,int(y)], mode=mode, name=y)
    fig.append_trace(d, 1, 1)
    return fig

if __name__ == '__main__':
    app.run_server(host='0.0.0.0', port=8051)

