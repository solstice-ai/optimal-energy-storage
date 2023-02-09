import plotly.graph_objs as go
from plotly import subplots


def generate_df_fig(df, time_from=None, time_to=None):
    if time_from is None:
        time_from = df.index[0]
    if time_to is None:
        time_to = df.index[-1]

    df_slice = df.loc[time_from:time_to, :]

    trace_gen = go.Scatter(x=df_slice.index,
                           y=df_slice['generation'].tolist(),
                           name="generation",
                           line=dict(color='green', width=2))
    trace_dem = go.Scatter(x=df_slice.index,
                           y=df_slice['demand'].tolist(),
                           name="demand",
                           line=dict(color='red', width=2, dash='dot'))
    trace_ti = go.Scatter(x=df_slice.index,
                          y=df_slice['tariff_import'].tolist(),
                          name="tariff - import",
                          line=dict(color='magenta', width=2))
    trace_te = go.Scatter(x=df_slice.index,
                          y=df_slice['tariff_export'].tolist(),
                          name="tariff - export",
                          line=dict(color='orange', width=2))
    trace_price = go.Scatter(x=df_slice.index,
                             y=df_slice['market_price'].tolist(),
                             name="market price",
                             line=dict(color='blue', width=2))

    fig = subplots.make_subplots(rows=4, cols=1,
                                 specs=[
                                     [{'rowspan': 2}],
                                     [None],
                                     [{'rowspan': 1}],
                                     [{'rowspan': 1}]
                                 ],
                                 shared_xaxes=True, print_grid=False)
    fig.append_trace(trace_gen, 1, 1)
    fig.append_trace(trace_dem, 1, 1)
    fig.append_trace(trace_ti, 3, 1)
    fig.append_trace(trace_te, 3, 1)
    fig.append_trace(trace_price, 4, 1)

    fig['layout']['yaxis1'].update({'title': 'W'})
    fig['layout']['yaxis2'].update({'title': '$ / kWh', 'rangemode': 'tozero'})
    fig['layout']['yaxis3'].update({'title': '$ / MWh'})
    fig['layout'].update(
        height=300,
        margin=go.layout.Margin(
            l=50,
            r=10,
            b=30,
            t=0,
            pad=0
        ),
    )

    return fig


def generate_solution_fig(
        df, solution,
        include_subfigs=['gendem', 'price', 'tariffs', 'charge_rate', 'soc', 'cost', 'net_impact'],
        exclude_subfigs=[],
        time_from=None, time_to=None
):
    if time_from is None:
        time_from = df.index[0]
    if time_to is None:
        time_to = df.index[-1]

    df_slice = df.loc[time_from:time_to, :]
    solution_slice = solution.loc[time_from:time_to, :]

    # Determine total number of subfigs.  There are probably cleaner ways to do this :)
    num_subfigs = len(include_subfigs)
    for subfig in exclude_subfigs:
        if subfig in include_subfigs:
            num_subfigs = num_subfigs - 1
    curr_subfig_num = 1

    fig = subplots.make_subplots(rows=num_subfigs, cols=1, shared_xaxes=True, print_grid=False,
                                 vertical_spacing=0.05,
                                 subplot_titles=[" "]*num_subfigs)

    if 'gendem' in include_subfigs and 'gendem' not in exclude_subfigs:
        trace_gen = go.Scatter(x=df_slice.index,
                               y=df_slice['generation'].tolist(),
                               name="generation",
                               line=dict(width=2))
        trace_dem = go.Scatter(x=df_slice.index,
                               y=df_slice['demand'].tolist(),
                               name="demand",
                               line=dict(width=2, dash='dot'))
        fig.append_trace(trace_gen, curr_subfig_num, 1)
        fig.append_trace(trace_dem, curr_subfig_num, 1)
        fig.update_yaxes(title_text="W", row=curr_subfig_num, col=1)
        fig.layout.annotations[curr_subfig_num-1].update(text="Demand and generation")
        curr_subfig_num = curr_subfig_num + 1

    if 'price' in include_subfigs and 'price' not in exclude_subfigs:
        trace_price = go.Scatter(x=df_slice.index,
                                 y=[p / 1000 for p in df_slice['market_price']],
                                 name="market price",
                                 line=dict(width=2),
                                 showlegend=False)
        fig.append_trace(trace_price, curr_subfig_num, 1)
        fig.update_yaxes(title_text="$/MWh", row=curr_subfig_num, col=1)
        fig.layout.annotations[curr_subfig_num-1].update(text="Spot market price")
        curr_subfig_num = curr_subfig_num + 1

    if 'tariffs' in include_subfigs and 'tariffs' not in exclude_subfigs:
        trace_ti = go.Scatter(x=df_slice.index,
                              y=df_slice['tariff_import'].tolist(),
                              name="tariff - import",
                              line=dict(width=2))
        trace_te = go.Scatter(x=df_slice.index,
                              y=df_slice['tariff_export'].tolist(),
                              name="tariff - export",
                              line=dict(width=2))
        # Arbitrage opportunity is range below min import and above max export ?
        # export_max = df_slice['tariff_export'].max()
        # import_min = df_slice['tariff_import'].min()
        # trace_ao = go.Scatter(
        #     x=[df_slice.index[0], df_slice.index[-1], df_slice.index[-1], df_slice.index[0]],
        #     y=[export_max, export_max, import_min, import_min],
        #     fill='toself',
        #     fillcolor='yellow',
        #     line=dict(color='yellow'),
        #     opacity=0.3,
        #     name='arbitrage_opportunity'
        # )
        # fig.append_trace(trace_ao, curr_subfig_num, 1)
        fig.append_trace(trace_ti, curr_subfig_num, 1)
        fig.append_trace(trace_te, curr_subfig_num, 1)
        fig.update_yaxes(title_text="$/kWh", row=curr_subfig_num, col=1)
        fig.layout.annotations[curr_subfig_num-1].update(text="Tariffs")
        curr_subfig_num = curr_subfig_num + 1

    if 'charge_rate' in include_subfigs and 'charge_rate' not in exclude_subfigs:
        trace_cr = go.Scatter(x=solution_slice.index,
                              y=solution_slice['charge_rate'],
                              name='charge rate',
                              line=dict(width=2),
                              showlegend=False)
        fig.append_trace(trace_cr, curr_subfig_num, 1)
        fig.update_yaxes(title_text="W", row=curr_subfig_num, col=1)
        fig.layout.annotations[curr_subfig_num-1].update(text="Charge rate")
        curr_subfig_num = curr_subfig_num + 1

    if 'net_impact' in include_subfigs and 'net_impact' not in exclude_subfigs:
        trace_gi = go.Scatter(x=solution_slice.index,
                              y=solution_slice['grid_impact'],
                              name='net grid impact',
                              showlegend=False)
        fig.append_trace(trace_gi, curr_subfig_num, 1)
        fig.update_yaxes(title_text="W", row=curr_subfig_num, col=1)
        fig.layout.annotations[curr_subfig_num-1].update(text="Net grid impact")
        curr_subfig_num = curr_subfig_num + 1

    if 'soc' in include_subfigs and 'soc' not in exclude_subfigs:
        trace_soc = go.Scatter(x=solution_slice.index,
                               y=solution_slice['soc'],
                               name='soc',
                               showlegend=False)
        fig.append_trace(trace_soc, curr_subfig_num, 1)
        fig.update_yaxes(title_text="%", range=[0, 100], row=curr_subfig_num, col=1)
        fig.layout.annotations[curr_subfig_num-1].update(text="State of charge")
        curr_subfig_num = curr_subfig_num + 1

    # Revenue and cost are inverse of one another
    if 'cost' in include_subfigs and 'cost' not in exclude_subfigs:
        trace_cost = go.Scatter(x=solution_slice.index,
                                y=solution_slice['accumulated_cost'],
                                name='cost',
                                showlegend=False)
        fig.append_trace(trace_cost, curr_subfig_num, 1)
        fig.update_yaxes(title_text="$", row=curr_subfig_num, col=1)
        fig.layout.annotations[curr_subfig_num-1].update(text="Cost")
        curr_subfig_num = curr_subfig_num + 1
    if 'revenue' in include_subfigs and 'revenue' not in exclude_subfigs:
        trace_revenue = go.Scatter(x=solution_slice.index,
                                   y=-1 * solution_slice['accumulated_cost'],
                                   name='revenue',
                                   showlegend=False)
        fig.append_trace(trace_revenue, curr_subfig_num, 1)
        fig.update_yaxes(title_text="$", row=curr_subfig_num, col=1)
        fig.layout.annotations[curr_subfig_num-1].update(text="Revenue")
        curr_subfig_num = curr_subfig_num + 1


    # fig['layout']['yaxis1'].update({'title': 'W'})
    # fig['layout']['yaxis2'].update({'title': 'W'})
    # fig['layout']['yaxis3'].update({'title': '%'})
    # fig['layout']['yaxis4'].update({'title': '$ / kWh', 'rangemode': 'tozero'})
    # fig['layout']['yaxis5'].update({'title': '$'})
    fig['layout'].update(
        height=120 * num_subfigs,
        margin=go.layout.Margin(
            l=50,
            r=10,
            b=30,
            t=30,
            pad=0
        ),
    )

    return fig


def generate_evaluation_fig(evaluation):
    """ Shows comparison of evaluation of different battery control strategies """
    traces = []
    for eval in evaluation:
        trace = go.Scatter(
            x=evaluation.index,
            y=evaluation[eval],
            mode='lines',
            name=eval,
        )
        traces.append(trace)
    layout = go.Layout(
        height=300,
        margin=go.layout.Margin(
            l=50,
            r=200,
            b=30,
            t=0,
            pad=0
        ),
        yaxis=dict(title='Cost ($)')
    )
    return go.Figure(data=traces, layout=layout)


def generate_schedule_charge_rate_fig(schedule_charge_rates):
    """ Shows charge rates of different controllers in a schedule """
    traces = []
    for controller in schedule_charge_rates:
        trace = go.Scatter(
            x=schedule_charge_rates.index,
            y=schedule_charge_rates[controller],
            mode='lines',
            name=controller,
        )
        traces.append(trace)
    layout = go.Layout(
        height=300,
        margin=go.layout.Margin(
            l=50,
            r=200,
            b=30,
            t=0,
            pad=0
        ),
        yaxis=dict(title='Charge rate (W)')
    )
    return go.Figure(data=traces, layout=layout)


def generate_schedule_near_optimal_fig(schedule_near_optimal):
    """ Shows which controllers are close to optimal """
    traces = []
    names = []

    controller_index = len(schedule_near_optimal.columns) - 1
    for controller in schedule_near_optimal:
        # Keep only ones, ditch zeros
        df = schedule_near_optimal[schedule_near_optimal[controller] == 1]
        trace = go.Scatter(
            x=df.index,
            y=[y * controller_index for y in df[controller]],
            mode='markers',
            name=controller,
            showlegend=False
        )
        traces.append(trace)
        names.append(controller)
        controller_index = controller_index - 1

    layout = go.Layout(
        height=40 + 20 * len(schedule_near_optimal.columns),
        margin=go.layout.Margin(
            l=50,
            r=200,
            b=30,
            t=0,
            pad=0
        ),
        yaxis=go.layout.YAxis(
            title='Controller',
            tickmode='array',
            tickvals=list(range(len(schedule_near_optimal.columns) - 1, -1, -1)),
            ticktext=names
        )
    )
    return go.Figure(data=traces, layout=layout)
