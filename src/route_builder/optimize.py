"""Closed-loop traveling-salesperson solution using OR-Tools."""

from .matrix import DrivingMatrix


def solve_closed_loop(matrix: DrivingMatrix, time_limit_seconds: int = 5) -> list[int]:
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2

    count = len(matrix.durations)
    if count < 2 or time_limit_seconds < 1:
        raise ValueError("A route needs at least two stops and a positive solve time")
    manager = pywrapcp.RoutingIndexManager(count, 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    def travel_time(from_index: int, to_index: int) -> int:
        origin = manager.IndexToNode(from_index)
        destination = manager.IndexToNode(to_index)
        return round(matrix.durations[origin][destination] * 1000)

    callback = routing.RegisterTransitCallback(travel_time)
    routing.SetArcCostEvaluatorOfAllVehicles(callback)
    options = pywrapcp.DefaultRoutingSearchParameters()
    options.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    options.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    options.time_limit.seconds = time_limit_seconds
    solution = routing.SolveWithParameters(options)
    if solution is None:
        raise ValueError("OR-Tools could not find a closed driving loop")
    order = []
    index = routing.Start(0)
    while not routing.IsEnd(index):
        order.append(manager.IndexToNode(index))
        index = solution.Value(routing.NextVar(index))
    if len(order) != count or set(order) != set(range(count)):
        raise ValueError("Optimizer returned an incomplete route")
    return order
