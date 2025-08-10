import plotly.express as px

def plot_line(df, x, y, title=""):
    fig = px.line(df, x=x, y=y, title=title)
    fig.update_layout(margin=dict(l=20, r=20, t=30, b=20))
    return fig

def plot_bar(df, x, y, title=""):
    fig = px.bar(df, x=x, y=y, title=title)
    fig.update_layout(margin=dict(l=20, r=20, t=30, b=20))
    return fig 