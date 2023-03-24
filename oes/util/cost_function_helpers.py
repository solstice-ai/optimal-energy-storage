import oes.util.utility as utility

def compute_import_export_costs(import_tariff, export_tariff, market_price, allow_market_participation = True):
    #!!ACR: Julian this might not be correct in your version? I think you mentioned this in our meeting
    if allow_market_participation:
        import_cost = import_tariff + market_price/1000
        export_cost = export_tariff + market_price/1000
        return import_cost, export_cost
    else: return import_tariff, export_tariff

def compute_state_transition_cost(grid_impact_kwh, import_tariff, export_tariff, market_price, allow_market_participation=True):
    import_cost, export_cost = compute_import_export_costs(import_tariff, export_tariff, market_price, allow_market_participation=allow_market_participation)
    if grid_impact_kwh > 0: # if exporting
        state_transition_cost = grid_impact_kwh * export_cost
    elif grid_impact_kwh < 0: # if importing
        state_transition_cost = grid_impact_kwh * import_cost
    else: # if neither
        state_transition_cost = 0
    return state_transition_cost

def compute_interval_cost(grid_impact_w, interval_size_hours, import_tariff, export_tariff, market_price, allow_market_participation = True):
    grid_impact_kwh = utility.power_to_energy(grid_impact_w, interval_size_hours)/1000.0

    interval_cost = compute_state_transition_cost(
                    grid_impact_kwh, 
                    import_tariff, 
                    export_tariff, 
                    market_price, 
                    allow_market_participation=allow_market_participation)
    return interval_cost