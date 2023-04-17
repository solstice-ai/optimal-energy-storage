def pretty_time(t: int) -> str:
    """
    Outputs elapsed time as user-friendly string.  Used e.g. to display running time of DP solution calculation.
    :param t: time in seconds
    """

    # Less than a minute?
    if t < 60:
        return str(int(t)) + "s"

    # Less than an hour, more than a minute?
    elif t < 60 * 60:
        return str(int(t / 60)) + "m " + str(int(t % 60)) + "s"

    # More than an hour?
    else:
        return str(int(t / (60 * 60))) + "h " + str(int(int(t / 60) % 60)) + "m " + str(int(t % 60)) + "s"
