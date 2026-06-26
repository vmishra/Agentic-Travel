from agentic_travel.data.loader import (
    default_graph_data_path,
    load_default_graph_store,
)
from agentic_travel.graph.models import TransportMode


def test_default_graph_path_exists() -> None:
    assert default_graph_data_path().is_file()


def test_default_store_loads_and_traverses() -> None:
    store = load_default_graph_store()
    city = store.get_city("city_bom")
    assert city is not None
    assert city.name == "Mumbai"
    assert len(store.cities_in_country("ctry_in")) == 2
    assert len(store.pois_in_city("city_goi")) == 6
    flights = store.connections_from("city_bom", mode=TransportMode.FLIGHT)
    assert {"city_goi", "city_dxb"} <= {e.target_id for e in flights}
