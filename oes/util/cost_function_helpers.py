import oes.util.utility as utility


def compute_state_transition_cost(grid_impact_kwh, import_tariff, export_tariff):
    if grid_impact_kwh > 0:  # if exporting
        state_transition_cost = grid_impact_kwh * export_tariff
    elif grid_impact_kwh < 0:  # if importing
        state_transition_cost = grid_impact_kwh * import_tariff
    else:  # if neither
        state_transition_cost = 0
    return state_transition_cost


def compute_interval_cost(grid_impact_w, interval_size_hours, import_tariff, export_tariff):
    grid_impact_kwh = utility.power_to_energy(grid_impact_w, interval_size_hours) / 1000.0

    return compute_state_transition_cost(
        grid_impact_kwh,
        import_tariff,
        export_tariff
    )
