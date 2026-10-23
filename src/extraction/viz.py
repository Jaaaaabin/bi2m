"""Extraction-stage visualization: histograms, 3D matplotlib displays, triangle
mesh exports, refined-slab plot. Never called from a hot path - only from the
facade, after extraction/post-processing has produced its data.
"""

import os

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

import ifcopenshell.geom
import ifcopenshell.util.shape

from .model_loader import get_file_prefix_code


def wall_width_histogram(display_walls, out_fig_path):
    if not display_walls:
        return

    values = [w["width"] for w in display_walls if "width" in w]

    fig = plt.figure(figsize=(10, 5))
    ax = plt.axes((0.0875, 0.1, 0.875, 0.875))
    ax.hist(values, weights=np.ones(len(values)) / len(values), bins=20, color="#bcbd22", edgecolor="black")
    ax.set_xlabel("Width of IfcWalls", color="black", fontsize=12)
    ax.set_ylabel("Percentage Frequency Distribution", color="black", fontsize=12)
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.set_xlim(xmin=0.0, xmax=max(values) + 0.1)

    plt.savefig(os.path.join(out_fig_path, "wall_width_histogram.png"), dpi=200)
    plt.close(fig)


def wall_length_histogram(display_walls, out_fig_path):
    if not display_walls:
        return

    values = [w["length"] for w in display_walls if "length" in w]

    fig = plt.figure(figsize=(10, 5))
    ax = plt.axes((0.0875, 0.1, 0.875, 0.875))
    ax.hist(values, weights=np.ones(len(values)) / len(values), bins=20, color="#bcbd22", edgecolor="black")
    ax.set_xlabel("Length of IfcWalls", color="black", fontsize=12)
    ax.set_ylabel("Percentage Frequency Distribution", color="black", fontsize=12)
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.set_xlim(xmin=0.0, xmax=max(values) + 1.0)

    plt.savefig(os.path.join(out_fig_path, "wall_length_histogram.png"), dpi=200)
    plt.close(fig)


def wall_orientation_histogram(display_walls, out_fig_path):
    if not display_walls:
        return

    values = [w["orientation"] for w in display_walls if "orientation" in w]

    fig = plt.figure(figsize=(10, 5))
    ax = plt.axes((0.0875, 0.1, 0.875, 0.875))
    ax.hist(values, weights=np.ones(len(values)) / len(values), bins=20, color="#bcbd22", edgecolor="black")
    ax.set_xlabel("Orientation of IfcWalls [0°,180°)", color="black", fontsize=12)
    ax.set_ylabel("Percentage Frequency Distribution", color="black", fontsize=12)
    ax.yaxis.set_major_formatter(PercentFormatter(1))
    ax.set_xticks(np.arange(0, 180, 30))
    ax.set_xlim(xmin=0, xmax=180 + 1.0)

    plt.savefig(os.path.join(out_fig_path, "wall_orientation_histogram.png"), dpi=200)
    plt.close(fig)


def wall_display(info_walls, info_curtainwalls, out_fig_path):
    display_walls = info_walls + info_curtainwalls
    wall_width_histogram(display_walls, out_fig_path)
    wall_length_histogram(display_walls, out_fig_path)
    wall_orientation_histogram(display_walls, out_fig_path)


def wall_column_floor_location_display(
    ifc_file_name, out_fig_path,
    info_st_walls, info_ns_walls, info_curtainwalls, id_st_walls, id_ns_walls, id_ct_walls,
    info_st_columns, info_floors, wall_x_values, wall_y_values,
    corner_x_value, corner_y_value, corner_z_value, main_directions,
    default_elev=25, default_azim=50,
    view_elev=None, view_azim=None,
    plot_main_plane_directions=False, plot_main_plane=False, plane_vector_length=1,
):
    fig = plt.figure(figsize=(12, 6))
    ax = fig.add_subplot(111, projection="3d")

    elev = view_elev if view_elev is not None else default_elev
    azim = view_azim if view_azim is not None else default_azim

    ax.view_init(elev=elev, azim=azim)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_zticks([])
    ax.grid(False)
    ax.axis("off")

    # Display Walls
    display_walls = info_st_walls + info_ns_walls + info_curtainwalls
    if display_walls:
        st_wall_values, ns_wall_values, ct_wall_values = [], [], []
        for w in display_walls:
            if "location" in w:
                if w["id"] in id_st_walls:
                    st_wall_values.append(w["location"])
                elif w["id"] in id_ns_walls:
                    ns_wall_values.append(w["location"])
                elif w["id"] in id_ct_walls:
                    ct_wall_values.append(w["location"])

        for st_v in st_wall_values:
            start_point, end_point = st_v
            xs, ys, zs = zip(start_point, end_point)
            ax.plot(xs, ys, zs, marker="s", color="black", linewidth=1.5, markersize=1, alpha=0.875, label="IfcWall(S)")

        for ns_v in ns_wall_values:
            start_point, end_point = ns_v
            xs, ys, zs = zip(start_point, end_point)
            ax.plot(xs, ys, zs, marker="s", color="grey", linewidth=1, markersize=1, label="IfcWall(N)")

        for ct_v in ct_wall_values:
            start_point, end_point = ct_v
            xs, ys, zs = zip(start_point, end_point)
            ax.plot(xs, ys, zs, marker="s", color="royalblue", linewidth=1, markersize=1, label="IfcWall(CT)")

    # Display Columns
    if info_st_columns:
        column_values = [c["location"] for c in info_st_columns if "location" in c]
        for v in column_values:
            start_point, end_point = v
            xs, ys, zs = zip(start_point, end_point)
            ax.plot(xs, ys, zs, marker="o", color="olivedrab", linewidth=1.5, markersize=1, alpha=0.375, label="IfcColumn(S)")

    # Display Floors
    values = [w["location"] for w in info_floors if "location" in w]
    values = [x for xs in values for x in xs]

    plotted_lines = set()

    for v in values:
        start_point, end_point = tuple(v[0]), tuple(v[1])
        line = tuple(sorted((start_point, end_point)))
        if line not in plotted_lines:
            plotted_lines.add(line)
            xs, ys, zs = zip(start_point, end_point)
            ax.plot(xs, ys, zs, marker="x", color="salmon", linewidth=3, markersize=0.25, alpha=0.35, label="IfcSlab")

    grid_size_x = max(abs(min(wall_x_values)), abs(max(wall_x_values)))
    grid_size_y = max(abs(min(wall_y_values)), abs(max(wall_y_values)))

    if plot_main_plane_directions:

        plot_shift_z = 5

        ax.quiver(
            corner_x_value, corner_y_value, corner_z_value - plot_shift_z * 1.5,
            0, 0, plane_vector_length * 1,
            color="tomato", arrow_length_ratio=0.3)

        if plot_main_plane:

            horizontal_x = np.linspace(-grid_size_x * 1.25, grid_size_x * 1.25, 5)
            horizontal_y = np.linspace(-grid_size_y * 1.25, grid_size_y * 1.25, 5)
            xx, yy = np.meshgrid(horizontal_x, horizontal_y)

            horizontal_z = np.zeros_like(xx)
            horizontal_z = horizontal_z - plot_shift_z

            ax.plot_surface(xx, yy, horizontal_z, alpha=0.2, color="tomato")

        if main_directions:

            for degree in main_directions:

                radian = np.deg2rad(degree)
                x = np.cos(radian)
                y = np.sin(radian)
                ax.quiver(
                    corner_x_value, corner_y_value, corner_z_value - plot_shift_z * 1.5,
                    plane_vector_length * x * 2, plane_vector_length * y * 2, 0,
                    color="navy", arrow_length_ratio=0.3)

                if plot_main_plane:

                    normal_vector = np.array([np.cos(radian), np.sin(radian), 0])
                    if degree == 90 or degree == 270:
                        v1 = np.array([1, 0, 0])
                    else:
                        v1 = np.array([-normal_vector[1], normal_vector[0], 0])

                    v2 = np.cross(normal_vector, v1)

                    u = np.linspace(-grid_size_x, grid_size_x, 5)
                    v = np.linspace(-grid_size_y, grid_size_y, 5)
                    uu, vv = np.meshgrid(u, v)

                    plane_points = (
                        corner_x_value + uu * v1[0] + vv * v2[0],
                        corner_y_value + uu * v1[1] + vv * v2[1],
                        (corner_z_value + uu * v1[2] + vv * v2[2]) * 0.5 - plot_shift_z,
                    )
                    ax.plot_surface(plane_points[0], plane_points[1], plane_points[2], alpha=0.2, color="skyblue")

    plt.tight_layout()

    plt.savefig(os.path.join(
        out_fig_path, get_file_prefix_code(ifc_file_name) + "_wall_column_floor_location_map.png"), dpi=200)
    plt.close(fig)


def export_triangle_geometry(settings, model, id=None, x_box=1, y_box=1, z_box=1):
    if not id:
        raise ValueError("please specify the Guid of the element")

    element = model.by_guid(id)
    shape = ifcopenshell.geom.create_shape(settings, element)
    matrix = ifcopenshell.util.shape.get_shape_matrix(shape)
    location = matrix[:, 3][0:3]

    grouped_verts = ifcopenshell.util.shape.get_vertices(shape.geometry)
    grouped_faces = ifcopenshell.util.shape.get_faces(shape.geometry)

    fig = plt.figure()
    ax = fig.add_subplot(111, projection="3d")
    ax.set_box_aspect([x_box, y_box, z_box])

    for fc in grouped_faces:
        vertices = grouped_verts[fc]
        vertices = np.vstack([vertices, vertices[0]])
        x, y, z = vertices[:, 0], vertices[:, 1], vertices[:, 2]
        ax.plot(x, y, z, linewidth=1, color="black", alpha=0.5)

    plt.title(id)
    plt.show()


def tempo_export_triangle_geometry_single_wall(settings, model, out_fig_path, ids=None,
                                                x_box=1, y_box=1, z_box=1, elev=30, azim=45):
    if not ids:
        raise ValueError("Please specify the GUID of the element")

    for id in ids:

        element = model.by_guid(id)
        shape = ifcopenshell.geom.create_shape(settings, element)
        matrix = ifcopenshell.util.shape.get_shape_matrix(shape)
        location = matrix[:, 3][0:3]

        grouped_verts = ifcopenshell.util.shape.get_vertices(shape.geometry)
        grouped_faces = ifcopenshell.util.shape.get_faces(shape.geometry)

        fig = plt.figure(figsize=(12, 8))
        ax = fig.add_subplot(111, projection="3d")
        ax.set_box_aspect([x_box, y_box, z_box])

        for fc in grouped_faces:
            vertices = grouped_verts[fc]
            poly3d = [[tuple(vertices[j]) for j in range(len(vertices))]]
            ax.add_collection3d(Poly3DCollection(poly3d, facecolors="w", linewidths=1, edgecolors="black", alpha=0.5))

        x_range = np.max(grouped_verts[:, 0]) - np.min(grouped_verts[:, 0])
        y_range = np.max(grouped_verts[:, 1]) - np.min(grouped_verts[:, 1])
        z_range = np.max(grouped_verts[:, 2]) - np.min(grouped_verts[:, 2])

        max_range = max(x_range, y_range, z_range)

        ax.set_xlim([np.min(grouped_verts[:, 0]) - max_range * 0.1, np.max(grouped_verts[:, 0]) + max_range * 0.1])
        ax.set_ylim([np.min(grouped_verts[:, 1]) - max_range * 0.1, np.max(grouped_verts[:, 1]) + max_range * 0.1])
        ax.set_zlim([np.min(grouped_verts[:, 2]) - max_range * 0.1, np.max(grouped_verts[:, 2]) + max_range * 0.1])

        ax.view_init(elev=elev, azim=azim)

        ax.set_title(id)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_zticks([])
        ax.grid(False)
        ax.axis("off")

        plt.tight_layout()
        plt.savefig(os.path.join(out_fig_path, str(id) + "triangle_meshes.png"), dpi=100)
        plt.close(fig)


def triangle_display_of_one_element(settings, element):

    shape = ifcopenshell.geom.create_shape(settings, element)
    matrix = ifcopenshell.util.shape.get_shape_matrix(shape)
    location = matrix[:, 3][0:3]

    location_array = np.array(location)
    grouped_verts = ifcopenshell.util.shape.get_vertices(shape.geometry)
    grouped_verts = location_array + grouped_verts
    grouped_faces = ifcopenshell.util.shape.get_faces(shape.geometry)

    poly3ds_per_element = []
    for fc in grouped_faces:
        vertices = grouped_verts[fc]
        poly3d = [[tuple(vertices[j]) for j in range(len(vertices))]]
        poly3ds_per_element.append(poly3d)

    return poly3ds_per_element, grouped_verts


def export_triangle_geometry_of_all_walls(settings, model, id_ns_walls, plates, out_fig_path,
                                           x_box=1, y_box=1, z_box=1, elev=45, azim=50):

    all_wall_ids = list(set(id_ns_walls))
    all_plate_ids = [wall_plate.GlobalId for wall_plate in plates]
    all_element_ids = all_wall_ids + all_plate_ids

    fig = plt.figure(figsize=(12, 8))
    ax = fig.add_subplot(111, projection="3d")
    ax.set_box_aspect([x_box, y_box, z_box])

    all_grouped_verts = None
    started = False
    for id in all_element_ids:

        element_edgecolor = None
        if id == "1ikpL435zCYA4QPkDWyd7c":
            element_edgecolor = "maroon"
        elif id == "1ikpL435zCYA4QPkDWyd4L":
            element_edgecolor = "gray"
        else:
            element_edgecolor = "lightskyblue"

        element = model.by_guid(id)
        poly3ds_per_element, grouped_verts_per_element = triangle_display_of_one_element(settings, element)

        if started:
            all_grouped_verts = np.vstack((all_grouped_verts, grouped_verts_per_element))
        else:
            all_grouped_verts = grouped_verts_per_element
            started = True

        for poly3d in poly3ds_per_element:
            ax.add_collection3d(Poly3DCollection(poly3d, facecolors="w", linewidths=1, edgecolors=element_edgecolor, alpha=0.5))

    x_range = np.max(all_grouped_verts[:, 0]) - np.min(all_grouped_verts[:, 0])
    y_range = np.max(all_grouped_verts[:, 1]) - np.min(all_grouped_verts[:, 1])
    z_range = np.max(all_grouped_verts[:, 2]) - np.min(all_grouped_verts[:, 2])
    max_range = max(x_range, y_range, z_range)

    ax.set_xlim([np.min(all_grouped_verts[:, 0]) - max_range * 0.1, np.max(all_grouped_verts[:, 0]) + max_range * 0.1])
    ax.set_ylim([np.min(all_grouped_verts[:, 1]) - max_range * 0.1, np.max(all_grouped_verts[:, 1]) + max_range * 0.1])
    ax.set_zlim([np.min(all_grouped_verts[:, 2]) - max_range * 0.1, np.max(all_grouped_verts[:, 2]) + max_range * 0.1])

    ax.view_init(elev=elev, azim=azim)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_zticks([])
    ax.grid(False)
    ax.axis("off")

    plt.tight_layout()
    plt.savefig(os.path.join(out_fig_path, str(elev) + str(azim) + "_triangle_meshes.png"), dpi=300)
    plt.close(fig)


def export_triangle_geometry_of_a_curtainwall(settings, model, plates, out_fig_path,
                                               x_box=1, y_box=1, z_box=1, elev=45, azim=50):

    all_plate_ids = [wall_plate.GlobalId for wall_plate in plates]
    all_element_ids = all_plate_ids

    fig = plt.figure(figsize=(30, 20))
    ax = fig.add_subplot(111, projection="3d")
    ax.set_box_aspect([x_box, y_box, z_box])

    all_grouped_verts = None
    started = False
    for id in all_element_ids:

        element_edgecolor = None
        if id == "1ikpL435zCYA4QPkDWyd7c":
            element_edgecolor = "maroon"
        elif id == "1ikpL435zCYA4QPkDWyd4L":
            element_edgecolor = "gray"
        else:
            element_edgecolor = "lightskyblue"

        element = model.by_guid(id)
        poly3ds_per_element, grouped_verts_per_element = triangle_display_of_one_element(settings, element)

        if started:
            all_grouped_verts = np.vstack((all_grouped_verts, grouped_verts_per_element))
        else:
            all_grouped_verts = grouped_verts_per_element
            started = True

        for poly3d in poly3ds_per_element:
            ax.add_collection3d(Poly3DCollection(poly3d, facecolors="w", linewidths=1, edgecolors=element_edgecolor, alpha=0.95))

    ax.scatter(all_grouped_verts[:, 0], all_grouped_verts[:, 1], all_grouped_verts[:, 2], color="black", s=8)

    x_range = np.max(all_grouped_verts[:, 0]) - np.min(all_grouped_verts[:, 0])
    y_range = np.max(all_grouped_verts[:, 1]) - np.min(all_grouped_verts[:, 1])
    z_range = np.max(all_grouped_verts[:, 2]) - np.min(all_grouped_verts[:, 2])
    max_range = max(x_range, y_range, z_range)

    ax.set_xlim([np.min(all_grouped_verts[:, 0]) - max_range * 0.1, np.max(all_grouped_verts[:, 0]) + max_range * 0.1])
    ax.set_ylim([np.min(all_grouped_verts[:, 1]) - max_range * 0.1, np.max(all_grouped_verts[:, 1]) + max_range * 0.1])
    ax.set_zlim([np.min(all_grouped_verts[:, 2]) - max_range * 0.1, np.max(all_grouped_verts[:, 2]) + max_range * 0.1])

    ax.view_init(elev=elev, azim=azim)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_zticks([])
    ax.grid(False)
    ax.axis("off")

    plt.tight_layout()
    plt.savefig(os.path.join(out_fig_path, "curtainwall_triangle_meshes.png"), dpi=300)
    plt.close(fig)


def refined_floor_slabs_display(info_floor_slabs, out_fig_path, ifc_file_name):

    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection="3d")

    norm = plt.Normalize(vmin=0, vmax=1)
    cmap = matplotlib.colormaps["coolwarm"]

    for st_z, loop, area in info_floor_slabs:
        color = cmap(norm(area))
        loop.append(loop[0])  # To close the loop
        loop_array = np.array(loop)
        ax.plot(loop_array[:, 0], loop_array[:, 1], loop_array[:, 2], color=color, alpha=0.5)

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = plt.colorbar(sm, ax=ax)
    cbar.set_label("Closed area of slab geometries (as % of the maximum closed area)", fontsize=14)
    cbar.set_ticks([0, 0.5, 1])
    cbar.set_ticklabels(["0%", "50%", "100%"])

    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_zticks([])
    ax.grid(False)
    ax.axis("off")

    plt.tight_layout()
    plt.savefig(os.path.join(
        out_fig_path, get_file_prefix_code(ifc_file_name) + "_refined_floor_slabs.png"), dpi=200)
    plt.close(fig)
