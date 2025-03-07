import streamlit as st
import folium
from streamlit_folium import folium_static, st_folium
import osmnx as ox
import networkx as nx
from folium.plugins import Draw, PolyLineTextPath
import gpxpy
import gpxpy.gpx
import urllib.parse


german_cities = [
    "Berlin", "Hamburg", "München", "Köln", "Frankfurt am Main", "Stuttgart", "Düsseldorf", "Leipzig", "Dortmund", "Essen",
    "Bremen", "Dresden", "Hannover", "Nürnberg", "Duisburg", "Bochum", "Wuppertal", "Bielefeld", "Bonn", "Münster",
    "Karlsruhe", "Mannheim", "Augsburg", "Wiesbaden", "Gelsenkirchen", "Mönchengladbach", "Braunschweig", "Chemnitz", "Kiel", "Aachen",
    "Halle (Saale)", "Magdeburg", "Freiburg im Breisgau", "Krefeld", "Lübeck", "Oberhausen", "Erfurt", "Mainz", "Rostock", "Kassel",
    "Hagen", "Saarbrücken", "Hamm", "Mülheim an der Ruhr", "Potsdam", "Ludwigshafen", "Oldenburg", "Leverkusen", "Osnabrück", "Solingen",
    "Heidelberg", "Herne", "Neuss", "Darmstadt", "Paderborn", "Regensburg", "Ingolstadt", "Würzburg", "Wolfsburg", "Ulm",
    "Heilbronn", "Offenbach am Main", "Göttingen", "Bottrop", "Trier", "Recklinghausen", "Pforzheim", "Reutlingen", "Bremerhaven", "Koblenz",
    "Bergisch Gladbach", "Jena", "Remscheid", "Erlangen", "Moers", "Siegen", "Hildesheim", "Salzgitter", "Cottbus", "Kaiserslautern",
    "Gütersloh", "Schwerin", "Witten", "Gera", "Iserlohn", "Ludwigsburg", "Esslingen am Neckar", "Zwickau", "Düren", "Ratingen",
    "Flensburg", "Lünen", "Villingen-Schwenningen", "Konstanz", "Marl", "Dessau-Roßlau", "Velbert", "Worms", "Minden", "Neumünster"
]


# Funktion zur Generierung eines Google Maps Links
def get_google_maps_link(route):
    base_url = "https://www.google.com/maps/dir/"
    waypoints = "/".join([f"{lat},{lon}" for lat, lon in route])
    return f"{base_url}{urllib.parse.quote(waypoints)}"


# Funktion zum Abrufen des Straßennetzwerks
def get_street_graph(location="Ludwigshafen, Germany"):
    G = ox.graph_from_place(location, network_type='walk', simplify=True)
    G.to_undirected()
    return G


# Funktion zur Kombination mehrerer Straßennetze (FUTURE)
def merge_graphs(cities):
    merged_graph = None
    for city in cities:
        G = get_street_graph(f"{city}, Germany")
        merged_graph = nx.compose(merged_graph, G) if merged_graph else G
    return merged_graph


# Funktion zur Anzeige der Karte mit Zeichenfunktion
def create_map():
    m = folium.Map(location=[49.48121, 8.44641], zoom_start=14)
    draw = Draw(export=True)
    draw.add_to(m)  # Erlaubt das Zeichnen von Linien
    return m


def export_to_gpx(route):
    gpx = gpxpy.gpx.GPX()
    gpx_track = gpxpy.gpx.GPXTrack()
    gpx.tracks.append(gpx_track)
    gpx_segment = gpxpy.gpx.GPXTrackSegment()
    gpx_track.segments.append(gpx_segment)

    for lat, lon in route:
        gpx_segment.points.append(gpxpy.gpx.GPXTrackPoint(lat, lon))

    return gpx.to_xml()


# Funktion zum Berechnen der optimalen Route
def solve_chinese_postman(G, marked_edges):
    print("G: ", G)

    nodes = set()

    # Extrahiere alle relevanten Knoten aus den markierten Kanten
    for edge in marked_edges:
        if len(edge) == 2:
            node1 = ox.distance.nearest_nodes(G, X=edge[0][0], Y=edge[0][1])
            node2 = ox.distance.nearest_nodes(G, X=edge[1][0], Y=edge[1][1])
            nodes.add(node1)
            nodes.add(node2)

    nodes = list(nodes)

    if len(nodes) < 2:
        st.error("Nicht genügend Knoten markiert, um eine Route zu berechnen.")
        return []

    # Erstelle ein vollständiges Graphenmodell für das TSP-Problem
    tsp_graph = nx.Graph()

    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            try:
                length = nx.shortest_path_length(G, source=nodes[i], target=nodes[j], weight='length')
                tsp_graph.add_edge(nodes[i], nodes[j], weight=length)
            except nx.NetworkXNoPath:
                st.error(f"Kein Pfad zwischen den Knoten {nodes[i]} und {nodes[j]} gefunden.")
                return []

    tsp_route = nx.approximation.traveling_salesman_problem(tsp_graph, cycle=True)

    # Konvertiere die TSP-Lösung in tatsächliche GPS-Koordinaten entlang des Graphen
    final_path = []
    total_length = 0
    for i in range(len(tsp_route) - 1):
        path = nx.shortest_path(G, source=tsp_route[i], target=tsp_route[i+1], weight='length')
        path_length = nx.shortest_path_length(G, source=tsp_route[i], target=tsp_route[i+1], weight='length')
        total_length += path_length
        final_path.extend([(G.nodes[n]['y'], G.nodes[n]['x']) for n in path])

    return final_path, total_length


# Funktion zur Extraktion der markierten Linien
def extract_marked_edges(data):
    marked_edges = []
    if isinstance(data, list):  # Falls die Daten eine Liste sind
        for feature in data:
            if 'geometry' in feature and feature['geometry']['type'] == 'LineString':
                coords = feature['geometry']['coordinates']
                marked_edges.append(coords)

    print("marked_edges: ", marked_edges)
    return marked_edges


# Streamlit App
st.title("Straßenmarkierung & Routing")
st.write("Markiere Straßen auf der Karte und berechne die optimale Route.")

# Karte anzeigen
map_ = create_map()
map_data = st_folium(map_, width=700, height=500, key="map")

selected_cities = st.multiselect("Wähle eine oder mehrere Städte:", list(german_cities), default="Ludwigshafen")

# Button zum Starten der Berechnung
if st.button("Route berechnen"):
    #G = get_street_graph()
    G = merge_graphs(selected_cities)
    drawn_features = map_data.get("all_drawings", [])  # Anpassung für erwartete Liste
    marked_edges = extract_marked_edges(drawn_features)

    if marked_edges:
        shortest_route, route_length = solve_chinese_postman(G, marked_edges)

        route_map = folium.Map(location=shortest_route[0], zoom_start=15)

        print("shortest_route: ", shortest_route)

        if shortest_route:                
            # Visualisierung der Route auf der Karte
            #for point in shortest_route:
            #    route_map.add_child(folium.CircleMarker([point[0], point[1]], radius=6.))
            polyline = folium.PolyLine(shortest_route, color='red', weight=3)
            route_map.add_child(polyline)

            folium.PolyLine(shortest_route, color='blue', weight=3).add_to(route_map)

            arrow = PolyLineTextPath(polyline, '\u2794', repeat=True, offset=7, attributes={'fill': 'black', 'font-weight': 'bold'})
            route_map.add_child(arrow)

            for edge in marked_edges:
                for coord in edge:
                    folium.CircleMarker(location=[coord[1], coord[0]],fill=True, fill_opacity=0.6, radius=6., color='red').add_to(route_map)

            folium_static(route_map)

            st.success(f"Optimale Route berechnet! Gesamtlänge: {route_length:.2f} Meter")

            gpx_data = export_to_gpx(shortest_route)
            st.download_button(label="GPX-Datei herunterladen", data=gpx_data, file_name="route.gpx", mime="application/xml")

            google_maps_link = get_google_maps_link(shortest_route)
            st.markdown(f"[Route auf Google Maps anzeigen]({google_maps_link})")
    else:
        st.warning("Bitte markiere Straßen auf der Karte, bevor du die Berechnung startest.")
