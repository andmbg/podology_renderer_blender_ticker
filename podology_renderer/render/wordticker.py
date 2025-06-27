from typing import List


class Appearance:
    def __init__(
        self,
        term,
        apid,
        timestamp=None,
        start=None,
        end=None,
        width=None,
    ):
        """One instance of a term appearing and disappearing on the canvas.

        An A. is a time-varying envelope that represents the presence of a term on a timeline.
        It holds a list of nodes defining the envelope's shape, which can be modified by
        adding breakpoints. However, we currently only manipulate it by merging two
        appearances together, which results in a new A. with a new set of nodes.
        You can instatiate an A. with either a `timestamp` + `envelope_width` (which will be
        used to set the start and end) or with a start and end time.

        Args:
            term (str): the word or term that appears.
            timestamp (float, optional): center of the object on the timeline. Must be None
              if start and end are given.
            start (float, optional): start time of the Appearance. Use with `end`.
            end (float, optional): end time of the Appearance. Use with `start`.
            envelope_width (int, optional): total length of the Appearance. Use with `timestamp`.
            smoothing (float, optional): degree of spline smoothing. Sensible values are .1-.9.
        """
        self.term = term
        self.apid = apid

        if timestamp is None:
            if start is None or end is None:
                raise ValueError(
                    "Either timestamp or both start and end must be provided."
                )
            self.start = start
            self.end = end
            self.width = end - start
        else:
            if start is not None or end is not None:
                raise ValueError("Cannot provide both timestamp and start/end.")
            if width is None or width <= 0:
                raise ValueError(
                    "Envelope width must be given with timestamp and be positive."
                )
            self.start = timestamp - width / 2
            self.end = timestamp + width / 2
            self.width = width

    def to_dict(self) -> dict:
        """Convert the appearance to a JSON-serializable dict."""
        return {
            "term": self.term,
            "apid": self.apid,
            "start": round(self.start, 2),
            "end": round(self.end, 2),
            "width": round(self.width, 2),
        }

    def frame(self, t: float) -> float:
        """Get the value of the appearance at time t.

        Returns:
            float: The value of the appearance at time t.
        """
        if t <= self.start:
            return 0.0
        elif self.end <= t:
            return 1.0
        else:
            # Linear interpolation between start and end:
            return (t - self.start) / (self.end - self.start)

    def __repr__(self):
        return f"Appearance({self.term}, {self.start}, {self.end})"

    @classmethod
    def merge(cls, a, b):
        """Merge two appearance envelopes into one.

        Assumes that the latter appearance has not been modified
        by adding breakpoints or merges.
        """
        if a.term != b.term:
            raise ValueError("Cannot merge appearances of different terms.")

        # Make sure a is the earlier one:
        if a.end > b.end:
            a, b = b, a

        # Make sure there is overlap:
        if a.end <= b.start:
            raise ValueError("Cannot merge non-overlapping appearances.")

        c = cls(a.term, a.apid, start=a.start, end=b.end)

        return c


class Ticker:

    def __init__(self):
        self.lanes = []
        self.fps = 24

    def add_lane(self):
        """Add a new lane for a term."""
        self.lanes.append([])

    def add_appearance(self, appearance: Appearance):
        """Add an appearance to the ticker, manage lane placement.

        Place the appearance in the bottom-most lane that has no other
        appearances overlapping into this appearance's extent. If no
        such lane exists, create a new one. This method takes care
        that appearances do not overlap.
        """
        # Try to place in existing lanes:
        for i, lane in enumerate(self.lanes):
            if lane == []:
                self.lanes[i].append(appearance)
                return
            else:
                this_lanes_last: Appearance = lane[-1]
                if this_lanes_last.end <= appearance.start:
                    self.lanes[i].append(appearance)
                    return

        # If no suitable lane found, create a new one
        self.lanes.append([appearance])

    def get_value(self, apid, t) -> float:
        """Get the value of an appearance at time t."""
        for lane in self.lanes:
            for appearance in lane:
                if appearance.apid == apid:
                    return appearance.frame(t)
        return 0.0

    def to_dict(self):
        """Convert the ticker to a JSON-serializable dict."""
        return {
            "lanes": [
                [appearance.to_dict() for appearance in lane] for lane in self.lanes
            ],
            "fps": self.fps,
            "end": self.end,
        }

    def update_last_frame(self):
        """Update the last frame of each appearance in the ticker."""
        self.end = max(appearance.end for lane in self.lanes for appearance in lane)


def plot_ticker(ticker):
    import numpy as np
    from plotly.subplots import make_subplots
    import plotly.graph_objects as go

    nlanes = len(ticker.lanes)
    fig = make_subplots(rows=nlanes, cols=1, shared_xaxes=True, vertical_spacing=0.005)

    for i, lane in enumerate(ticker.lanes):
        for j, appearance in enumerate(lane):
            x = np.linspace(appearance.start, appearance.end, 100)
            y = [appearance.frame(k) for k in x]
            fig.add_trace(
                go.Scatter(
                    x=x,
                    y=y,
                    mode="lines",
                    name=appearance.apid,
                    line=dict(width=1, color="blue"),
                ),
                row=nlanes - i,
                col=1,
            )
            fig.add_trace(
                go.Scatter(
                    x=[min(x), max(x), max(x), min(x)],
                    y=[min(y), min(y), max(y), max(y)],
                    mode="lines",
                    fill="toself",
                    fillcolor="rgba(100, 100, 200, 0.1)",
                    line=dict(width=0, color="rgba(0, 0, 0, 0)"),
                    hoverinfo="skip",
                ),
                row=nlanes - i,
                col=1,
            )

    fig.update_layout(
        height=600,
        showlegend=False,
        margin=dict(l=20, r=20, t=20, b=20),
        plot_bgcolor="rgba(255,255,255, 1)",
        paper_bgcolor="rgba(235,235,235, 1)",
    )

    fig.update_yaxes(
        showticklabels=False,
        ticks="",
        gridcolor="rgba(0, 0, 0, 0.1)",
        range=(0.0, 1.0),
    )

    fig.update_xaxes(
        showgrid=False,
    )

    return fig


def ticker_from_timed_naments(named_entities: List[tuple], envelope_width: int = 120):
    """Create a Ticker object with its lanes and timing.

    Take a list of token-timing pairs, create a collection of lanes in each of which
    the tokens are placed as Appearances with the set envelope width, taking care of
    overlaps.

    Args:
        named_entities (List[tuple]): list of tuples (token: str, center: float)
            [temporal center of the appearance]
        envelope_width (int): Width of the envelope for each appearance in seconds.
    Returns:
        Ticker: A Ticker object with lanes filled with Appearances.
    """
    import pandas as pd

    df = pd.DataFrame(named_entities, columns=["token", "center"])
    df.sort_values(["token", "center"], inplace=True)
    df["enum"] = df.groupby("token").cumcount()
    df["apid"] = (
        df.token.str.replace(" ", "_").str.lower() + "." + df["enum"].astype(str)
    )

    appearances = []

    for type, grp in df.groupby("token"):
        # In app_group, all tokens have an Appearance, even if they overlap temporally:
        app_group = [
            Appearance(
                term=type,
                apid=row["apid"],
                timestamp=row["center"],
                width=envelope_width,
            )
            for _, row in grp.iterrows()
        ]
        app_group.sort(key=lambda x: x.start)

        # Merge overlapping appearances within the appearance group:
        # Look at first and second appearance, if 1st is untouched; send to
        # result list; if 2nd overlaps with 1st, merge them and continue with the next
        # appearance (which may also overlap with the merged one) until no more
        # overlaps are found - send the merged appearance to the result list.
        merged_group = []
        current = app_group[0]
        for nxt in app_group[1:]:
            if current.end < nxt.start:
                merged_group.append(current)
                current = nxt
            else:
                current = Appearance.merge(current, nxt)
        merged_group.append(current)
        appearances.extend(merged_group)

    appearances.sort(key=lambda x: x.start)

    ticker = Ticker()
    for appearance in appearances:
        ticker.add_appearance(appearance)

    ticker.update_last_frame()

    return ticker
