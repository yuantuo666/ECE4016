# Implemeted: BOLA algorithm
# Reference: https://github.com/Dash-Industry-Forum/dash.js/blob/e621627c988cb3d61144c960afb021c97669804e/src/streaming/rules/abr/BolaRule.js#L495
# Reference: https://arxiv.org/pdf/1601.06748

import math
import json

BUFFER_TIME_DEFAULT = 12  # Default buffer time, from https://github.com/Dash-Industry-Forum/dash.js/blob/development/src/streaming/models/MediaPlayerModel.js#L35
MINIMUM_BUFFER_S = 10  # p in paper
MINIMUM_BUFFER_PER_BITRATE_LEVEL_S = 2


def handle_bola(bola_state, buffer_level, bandwidth):
    quality_index = None
    max_score = -float("inf")
    for i, bitrate in enumerate(bola_state["bitrates"]):
        # maximize target = (V * (υm - 1 + γp) - Q) / Sm. Fig. 6, line 6 in paper
        score = (
            bola_state["Vp"] * (bola_state["utilities"][i] - 1 + bola_state["gp"])
            - buffer_level
        ) / bitrate
        if score > max_score:
            max_score = score # maximize the score
            quality_index = i

    # Here implement the "BOLA-O" variant: when network bandwidth lies between two encoded bitrate levels, stick to the lowest level.
    selected_bitrate = bola_state["bitrates"][quality_index]
    if selected_bitrate > bandwidth:
        quality_index = max(0, quality_index - 1)

    return quality_index


def initialize_bola_state(bitrates):

    # calculate logarithmic utility values
    utilities = [math.log(b) for b in bitrates]
    utilities = [u - utilities[0] + 1 for u in utilities]

    highest_utility_index = utilities.index(max(utilities))

    buffer_time = max(
        BUFFER_TIME_DEFAULT,
        MINIMUM_BUFFER_S + MINIMUM_BUFFER_PER_BITRATE_LEVEL_S * len(bitrates),
    )

    # If using Math.log utilities, we can choose Vp and gp to always prefer bitrates[0] at minimumBufferS and bitrates[max] at bufferTarget.
    # (Vp * (utility + gp) - bufferLevel) / bitrate has the maxima described when:
    # Vp * (utilities[0] + gp - 1) === minimumBufferS and Vp * (utilities[max] + gp - 1) === bufferTarget
    # giving:
    gp = (utilities[highest_utility_index] - 1) / (buffer_time / MINIMUM_BUFFER_S - 1)
    Vp = MINIMUM_BUFFER_S / gp

    return {
        "bitrates": bitrates,  # Sm in paper, supported bitrates
        "utilities": utilities,  # υm in paper, utility values, get by ln(bitrate/bitrate[0])
        "Vp": Vp,  # V in paper, control parameter in Lyapunov optimization
        "gp": gp,  # γp in paper, rebufferring avoidance parameter
    }


# Entry point function for selecting bitrate
def student_entrypoint(
    Measured_Bandwidth,
    Previous_Throughput,
    Buffer_Occupancy,
    Available_Bitrates,
    Video_Time,
    Chunk,
    Rebuffering_Time,
    Preferred_Bitrate,
):
    # init the BOLA
    bitrates_keys = list(Available_Bitrates.keys())
    bitrates_keys = [int(k) for k in bitrates_keys]

    # Check if bola_state is already initialized, if not, initialize it
    global bola_state
    if "bola_state" not in globals():
        bola_state = initialize_bola_state(bitrates_keys)

    # select the bitrate based on BOLA algorithm
    selected_bitrate = handle_bola(
        bola_state, Buffer_Occupancy["time"], Measured_Bandwidth
    )

    # Print the log
    rate_str = ""
    for i, (k, v) in enumerate(Available_Bitrates.items()):
        if i == selected_bitrate:
            rate_str += f"✅{int(k)/1000000:.2f}Mbps: {v}, "
        else:
            rate_str += f"❌{int(k)/1000000:.2f}Mbps: {v}, "
    rate_str = rate_str[:-2]

    print(
        f"[{Chunk['current']}, time={Video_Time:.2f}, rebuff={Rebuffering_Time:.2f}] {Measured_Bandwidth/1000000:.2f}Mbps, buffer={Buffer_Occupancy['time']:.2f}, rate={rate_str}"
    )

    return bitrates_keys[selected_bitrate]


if __name__ == "__main__":
    test = '{"Measured Bandwidth": 5000000.0, "Previous Throughput": 0, "Buffer Occupancy": {"size": 40000000, "current": 0, "time": 0}, "Available Bitrates": {"500000": 125223, "1000000": 250784, "5000000": 1243825}, "Video Time": 0, "Chunk": {"left": 30, "time": 2, "current": "0"}, "Rebuffering Time": 0, "Preferred Bitrate": null, "exit": 0}'
    jsonargs = json.loads(test)

    v = student_entrypoint(
        jsonargs["Measured Bandwidth"],
        jsonargs["Previous Throughput"],
        jsonargs["Buffer Occupancy"],
        jsonargs["Available Bitrates"],
        jsonargs["Video Time"],
        jsonargs["Chunk"],
        jsonargs["Rebuffering Time"],
        jsonargs["Preferred Bitrate"],
    )
    print(v)
