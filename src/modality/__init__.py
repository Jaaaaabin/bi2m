"""Token levels over an IFC model.

declared_grid  the model's declared IfcGrid axes in world plan metres, and the
               cells they cut (the shared layer)
grid_words     L1: one symbol per grid cell - which of column, beam and wall
               the cell holds - read as words along rows, columns and storeys
facade_bands   L0: one token per element along each facade run, class plus
               width, cut into bays where declared axes cross the facade
grid_lines     the declared axes as viewer line specs, one variant per
               distinct storey grid
"""
