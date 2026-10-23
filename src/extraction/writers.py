"""JSON serialization for extraction outputs."""

import os

from toolsQuickUtils import remove_duplicate_dicts

from io_utils import write_json


def write_dict_floors(info_floors, out_fig_path):
    dict_info_floors = remove_duplicate_dicts(info_floors)
    write_json(os.path.join(out_fig_path, "info_floors.json"), dict_info_floors)


def write_dict_floor_slabs(info_unique_floor_slabs, out_fig_path):
    write_json(os.path.join(out_fig_path, "info_floor_slabs.json"), info_unique_floor_slabs)


def write_dict_columns(info_st_columns, out_fig_path):
    dict_info_columns = remove_duplicate_dicts(info_st_columns)
    write_json(os.path.join(out_fig_path, "info_columns.json"), dict_info_columns)


def write_dict_walls(info_st_walls, info_ns_walls, info_curtainwalls, out_fig_path):

    dict_info_walls = remove_duplicate_dicts(info_st_walls)
    if dict_info_walls:
        write_json(os.path.join(out_fig_path, "info_st_walls.json"), dict_info_walls)

    dict_info_walls = remove_duplicate_dicts(info_ns_walls)
    if dict_info_walls:
        write_json(os.path.join(out_fig_path, "info_ns_walls.json"), dict_info_walls)

    dict_info_walls = remove_duplicate_dicts(info_curtainwalls)
    if dict_info_walls:
        write_json(os.path.join(out_fig_path, "info_ct_walls.json"), dict_info_walls)
