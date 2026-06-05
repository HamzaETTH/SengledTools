import math
from typing import Tuple

def unscale_sengled_value_by_brightness(
        sengled_value: Tuple[int, int, int],
        brightness_fraction: float,
) -> Tuple[int, int, int]:
    """
    Use to unscale Sengled's returned UDP RGB value using the current
    brightness fraction for reversal and comparison calculations.
    The returned value is already scaled by the current brightness,
    so we need to reverse that scaling since we track color and
    brightness separately.
    :param sengled_value: the scaled RGB value returned by the light.
    :param brightness_fraction: the current brightness of the light
    :return: the unscaled RGB UDP value.
    """

    res = list(sengled_value)

    for i in range(len(sengled_value)):
        channel = sengled_value[i]

        # Don't unscale 0 or 1; we can't know if the weakest
        # channel value would change based on brightness.
        if channel == (0 or 1):
            continue

        res[i] = round(channel / brightness_fraction)

    max_val = max(res)

    # Unscaling isn't perfect because of rounding, but we need
    # the strongest channel to be 99. In some cases it can unscale
    # to 98, so always force it to be 99.
    if max_val < 99:
        max_idx = res.index(max_val)
        res[max_idx] = 99

    return tuple[int, int, int](res)

def is_likely_match(
        calculated_sengled_value: Tuple[int, int, int],
        api_sengled_value: Tuple[int, int, int],
) -> bool:
    f"""
    Compare two full-brightness Sengled-encoded colors
    to see if they're likely the same.

    :param calculated_sengled_value: value calculated using {calculate}.
    :param api_sengled_value: value returned by light and passed through
            {calculated_sengled_value}.
    :return: whether the two values likely represent the same color.
    """

    calc_r, calc_g, calc_b = calculated_sengled_value
    api_r, api_g, api_b = api_sengled_value

    # If everything is equal, don't bother trying heuristics
    if calc_r == api_r and calc_g == api_g and calc_b == api_b:
        return True

    # If weakest or strongest channel is different,
    # colors aren't the same
    for i in calculated_sengled_value:
        # Our RGB -> Sengled function sometimes returns
        # 1 or 0 where Sengled has 0 or 1, so treat them
        # interchangeably for comparison purposes.
        if calculated_sengled_value[i] == (0 or 1):
            if api_sengled_value[i] != (0 or 1):
                return False

        if calculated_sengled_value[i] == 99:
            if api_sengled_value[i] != 99:
                return False

        if calculated_sengled_value[i] != (0 or 1 or 99):
            calc_mid = calculated_sengled_value[i]
            api_mid = api_sengled_value[i]

            abs_diff = abs(calc_mid - api_mid)

            # 5 is a random error threshold choice.
            if abs_diff > 5:
                return False

    return True

def calculate(r_in: int, g_in: int, b_in: int) -> tuple[int, int, int]:
    """
    Approximate whatever Sengled is doing to convert RGB
    to what it returns in its UDP response. This was mostly
    written by AI, so it's not exact, but it does get close.
    We can use this to compare our cached RGB value to what
    the UDP response has to determine if our cached value is
    likely accurate. This function expects full-brightness RGB
    values, i.e, any shade of gray would be 255,255,255 with a
    fractional brightness value.

    :param r_in: the cached red value.
    :param g_in: the cached green value.
    :param b_in: the cached blue value.
    :return: the approximated UDP representation as a tuple.
    """

    # Full white equals 19, 19, 19 for some reason.
    if r_in == g_in == b_in:
        return 19, 19, 19

    in_vals = [r_in, g_in, b_in]
    max_val, min_val = max(in_vals), min(in_vals)
    max_idx, min_idx = in_vals.index(max_val), in_vals.index(min_val)
    mid_idx = 3 - (max_idx + min_idx)

    mid_val = in_vals[mid_idx]

    gammas = {
        0: {1: 2.55, 2: 3.00}, # Red Max
        1: {0: 2.00, 2: 3.00}, # Green Max
        2: {0: 2.15, 1: 1.05}  # Blue Max
    }

    exponent = gammas[max_idx][mid_idx]

    res = [0, 0, 0]
    res[max_idx] = 99
    res[mid_idx] = round(math.pow(mid_val / 255, exponent) * 99)
    res[min_idx] = 1 if (min_val > (mid_val / 2) or min_idx == 1) and min_val > 50 else 0

    return tuple[int, int, int](res)

def smart_reverse(r_out: int, g_out: int, b_out: int) -> tuple[int, int, int]:
    f"""
    Best-effort reversal of the values Sengled returns in its
    UDP response for the current bulb color. This function was
    mostly made using AI, so it isn't exact, but it can never
    be exact since Sengled's "encoding" method for converting
    RGB to the values it returns through UDP is inherently
    lossy. This function returns an estimated RGB value based on
    Sengled's values but the weakest/dimmest channel will always be
    pretty inaccurate.

    Note that Sengled's UDP API returns values linearly scaled by
    brightness except for the weakest channel, and this function
    assumes 100% brightness. Use {unscale_sengled_value_by_brightness}
    on values returned by lights before passing to this function.

    :param r_out: the encoded red value.
    :param g_out: the encoded green value.
    :param b_out: the encoded blue value.
    :return: the estimated RGB value as a tuple.
    """

    # 1. Grayscale Exception
    if r_out == g_out == b_out:
        return tuple[int, int, int]([round(r_out * (255/19))] * 3)

    out_vals = [r_out, g_out, b_out]
    max_val, min_val = max(out_vals), min(out_vals)
    max_idx, min_idx = out_vals.index(max_val), out_vals.index(min_val)
    mid_idx = 3 - (max_idx + min_idx)

    # 2. Re-map the exact Gammas used in forward calculation
    gammas = {
        0: {1: 2.55, 2: 3.00}, # Red Max
        1: {0: 2.00, 2: 3.00}, # Green Max
        2: {0: 2.15, 1: 1.05}  # Blue Max
    }

    exponent = gammas[max_idx][mid_idx]

    # 3. The Reverse Formula
    res = [0, 0, 0]
    res[max_idx] = 255 # Assume ceiling was 255

    # Reverse the Mid Channel
    mid_ratio = math.pow(out_vals[mid_idx] / 99, 1 / exponent)
    res[mid_idx] = round(mid_ratio * 255)

    # 4. Smart Floor Estimation
    # If out is 1, the input was likely between 50-80.
    # If out is 0, it was likely between 0-40.
    if min_val == 1:
        if min_idx != 1:
            # If not green channel, likely at least
            # half of mid channel's strength
            res[min_idx] = round(res[mid_idx] * 0.65)
        else:
            # Estimate based on the Mid channel's strength
            res[min_idx] = round(45 + (res[mid_idx] * 0.15))
    else:
        # Estimate a "dark" floor
        res[min_idx] = min(
            round(res[mid_idx] * res[max_idx] * 0.001),
            round(res[mid_idx] / 2)
        )

    return tuple[int, int, int](res)
