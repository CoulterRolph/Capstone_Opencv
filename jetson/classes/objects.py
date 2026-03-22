# class.py 
# contains the class definition for the Tcubed object


#print("LOADING OBJECTS.PY")

# image point on (2D)
class img_point:
    def __init__(self, x=0.0, y=0.0):
        self.x = float(x)
        self.y = float(y)

    def set(self, x, y):
        self.x = float(x)
        self.y = float(y)

    def clear(self):
        self.x = 0
        self.y = 0

    def __str__(self):
        return f"({self.x}, {self.y})"

class player:
    def __init__(self, name, position=None):
        self.name = name
        self.position = position if position is not None else img_point()
    
    def set_name(self, name):
        self.name = name

    def set_position(self, position):
        self.position = position

    def set_position_xy(self, x, y):
        self.position.set(x, y)

    def __str__(self):
        return f"Player(name={self.name}, position={self.position})"

class table:
    def __init__(self, corners=None, net_position=None):
        self.corners = corners if corners is not None else [
            img_point(), img_point(), img_point(), img_point()
        ]

        self.net_position = net_position if net_position is not None else [
            img_point(), img_point()
        ]

    def set_corner(self, index, point):
        self.corners[index] = point

    def set_corner_xy(self, index, x, y):
        self.corners[index].set(x, y)

    def set_net_position(self, index, point):
        self.net_position[index] = point

    def set_net_position_xy(self, index, x, y):
        self.net_position[index].set(x, y)

    def __str__(self):
        corner_text = ", ".join(str(corner) for corner in self.corners)
        net_text = ", ".join(str(point) for point in self.net_position)
        return f"Table(corners=[{corner_text}], net_position=[{net_text}])"

