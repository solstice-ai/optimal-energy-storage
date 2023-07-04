import plotly.graph_objs as go
from plotly import subplots


def generate_scenario_fig(df, time_from=None, time_to=None):
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

    fig = subplots.make_subplots(rows=3, cols=1,
                                 specs=[
                                     [{'rowspan': 2}],
                                     [None],
                                     [{'rowspan': 1}],
                                 ],
                                 shared_xaxes=True, print_grid=False)
    fig.append_trace(trace_gen, 1, 1)
    fig.append_trace(trace_dem, 1, 1)
    fig.append_trace(trace_ti, 3, 1)
    fig.append_trace(trace_te, 3, 1)

    fig['layout']['yaxis1'].update({'title': 'W'})
    fig['layout']['yaxis2'].update({'title': '$ / kWh', 'rangemode': 'tozero'})
    fig['layout'].update(
        height=250,
        margin=go.layout.Margin(
            l=50,
            r=10,
            b=30,
            t=30,
            pad=0
        ),
    )

    return fig


def generate_solution_fig(
        df, solution,
        include_subfigs=['gendem', 'tariffs', 'charge_rate', 'soc', 'cost', 'net_impact'],
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

    if 'tariffs' in include_subfigs and 'tariffs' not in exclude_subfigs:
        trace_ti = go.Scatter(x=df_slice.index,
                              y=df_slice['tariff_import'].tolist(),
                              name="tariff - import",
                              line=dict(width=2))
        trace_te = go.Scatter(x=df_slice.index,
                              y=df_slice['tariff_export'].tolist(),
                              name="tariff - export",
                              line=dict(width=2))
        fig.append_trace(trace_ti, curr_subfig_num, 1)
        fig.append_trace(trace_te, curr_subfig_num, 1)
        fig.update_yaxes(title_text="$/kWh", row=curr_subfig_num, col=1)
        fig.layout.annotations[curr_subfig_num-1].update(text="Tariffs")
        curr_subfig_num = curr_subfig_num + 1

    if 'charge_rate' in include_subfigs and 'charge_rate' not in exclude_subfigs:
        trace_cr = go.Scatter(x=solution_slice.index,
                              y=solution_slice['charge_rate_actual'],
                              name='charge rate',
                              line=dict(width=2),
                              showlegend=False)
        fig.append_trace(trace_cr, curr_subfig_num, 1)
        fig.update_yaxes(title_text="W", row=curr_subfig_num, col=1)
        fig.layout.annotations[curr_subfig_num-1].update(text="Charge rate")
        curr_subfig_num = curr_subfig_num + 1

    if 'solar_curtailment' in include_subfigs and 'solar_curtailment' not in exclude_subfigs:
        trace_sc = go.Scatter(x=solution_slice.index,
                              y=solution_slice['solar_curtailment'],
                              name='solar curtailment',
                              showlegend=False)
        fig.append_trace(trace_sc, curr_subfig_num, 1)
        fig.update_yaxes(title_text="W", row=curr_subfig_num, col=1)
        fig.layout.annotations[curr_subfig_num-1].update(text="Solar curtailment")
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
                               y=solution_slice['soc_actual'],
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


def generate_evaluation_fig(evaluation, show_as_revenue=False):
    """
    Shows comparison of evaluation of different battery control strategies
    Default is to show cost.  When show_as_revenue=True, instead shows as revenue (inverse of cost)
    """
    traces = []
    for eval in evaluation:
        if show_as_revenue:
            y_vals = -1 * evaluation[eval]
        else:
            y_vals = evaluation[eval]
        trace = go.Scatter(
            x=evaluation.index,
            y=y_vals,
            mode='lines',
            name=eval,
        )
        traces.append(trace)

    if show_as_revenue:
        yaxis = dict(title='Revenue ($)')
    else:
        yaxis = dict(title='Cost ($)')

    layout = go.Layout(
        height=300,
        margin=go.layout.Margin(
            l=50,
            r=200,
            b=30,
            t=0,
            pad=0
        ),
        yaxis = yaxis,
    )
    return go.Figure(data=traces, layout=layout)


def generate_schedule_charge_rate_fig(scheduler):
    """ Shows charge rates of different controllers in a schedule """
    traces = []
    for controller in scheduler.charge_rates_all:
        if controller == 'DN':
            continue
        trace = go.Scatter(
            x=scheduler.charge_rates_all.index,
            y=scheduler.charge_rates_all[controller],
            mode='lines',
            name=controller,
        )
        traces.append(trace)
    traces.append(go.Scatter(
        x=scheduler.solution_optimal.index,
        y=scheduler.solution_optimal['charge_rate'],
        mode='lines',
        name='optimal'
    ))
    layout = go.Layout(
        height=300,
        margin=go.layout.Margin(
            l=50,
            r=200,
            b=30,
            t=30,
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
        if controller == 'DN':
            continue
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
            t=30,
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


def generate_schedule_fig(schedule):
    controllers = {}
    for ts, c_name in schedule.items():
        if c_name not in controllers.keys():
            controllers[c_name] = []
        controllers[c_name].append(ts)

    traces = []
    for c_name, timestamps in controllers.items():
        traces.append(go.Scatter(
            x=timestamps,
            y=[1] * len(timestamps),
            mode='markers',
            name=c_name,
        ))

    layout = go.Layout(
        height=150,
        margin=go.layout.Margin(
            l=50,
            r=200,
            b=30,
            t=30,
            pad=0
        ),
        yaxis=go.layout.YAxis(
            visible=False
        )
    )
    return go.Figure(data=traces, layout=layout)
