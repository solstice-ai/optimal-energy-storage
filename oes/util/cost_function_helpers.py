from oes.util.conversions import power_to_energy


def compute_state_transition_cost(grid_impact_wh: float, import_tariff: float, export_tariff: float) -> float:
    if grid_impact_wh > 0:  # if exporting
        state_transition_cost = grid_impact_wh/1000 * export_tariff
    elif grid_impact_wh < 0:  # if importing
        state_transition_cost = grid_impact_wh/1000 * import_tariff
    else:  # if neither
        state_transition_cost = 0
    return state_transition_cost


def compute_interval_cost(
        grid_impact_w: float, interval_size_hours: int, import_tariff: float, export_tariff: float) -> float:
    grid_impact_wh = grid_impact_w * interval_size_hours

    return compute_state_transition_cost(
        grid_impact_wh,
        import_tariff,
        export_tariff
    )
