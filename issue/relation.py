from calibration.revisions import ScenarioRevision
from strips.stations import StationMap


def freeze_relative_evidence(revision: ScenarioRevision, stations: StationMap) -> dict:
    # Subtracting the anchor is linear, so projection commutes with convex mixing.
    points = tuple(dict.fromkeys(
        tuple(value - row[0] for value in row[1:]) for row in revision.batch.rows
    ))
    return {
        'stations': stations.to_payload(),
        'relative_points': [[str(value) for value in point] for point in points],
    }
