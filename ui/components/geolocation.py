import os
import streamlit.components.v1 as components

component_dir = os.path.join(os.path.dirname(__file__), 'geo_component')
_component_func = components.declare_component('get_geolocation', path=component_dir)

def get_geolocation(key=None):
    return _component_func(key=key, default=None)
