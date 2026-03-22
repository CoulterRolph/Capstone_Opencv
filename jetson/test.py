
from classes.objects import img_point, player, table


def test_class():
    print("=== TESTING img_point ===")
    pt = img_point(10, 20)
    print("Initial point:", pt)

    pt.set(30, 40)
    print("After set(30, 40):", pt)

    pt.clear()
    print("After clear():", pt)

    print("\n=== TESTING player ===")
    trainee = player("Josh")
    print("Initial player:", trainee)

    trainee.set_name("Joshua")
    print("After set_name('Joshua'):", trainee)

    trainee.set_position_xy(100, 200)
    print("After set_position_xy(100, 200):", trainee)

    new_pos = img_point(300, 400)
    trainee.set_position(new_pos)
    print("After set_position(img_point(300, 400)):", trainee)

    print("Accessing player fields directly:")
    print("Name:", trainee.name)
    print("Position x:", trainee.position.x)
    print("Position y:", trainee.position.y)

    print("\n=== TESTING table ===")
    ping_table = table()
    print("Initial table:")
    print(ping_table)

    # Set corners and net positions (index, x, y)
    ping_table.set_corner_xy(0, 100, 100)
    ping_table.set_corner_xy(1, 500, 100)
    ping_table.set_corner_xy(2, 500, 300)
    ping_table.set_corner_xy(3, 100, 300)

    ping_table.set_net_position_xy(0,300, 200)
    ping_table.set_net_position_xy(1,300, 200)

    print("\nAfter setting corners and net:")
    print(ping_table)

    print("\nAccessing table values directly:")

    for i in range(len(ping_table.corners)):
        print(f"Corner{i}, x = {ping_table.corners[i].x}, y = {ping_table.corners[i].y}\n")
    
    for j in range(len(ping_table.net_position)):
        print(f"Net {j}, x = {ping_table.net_position[j].x}, y = {ping_table.net_position[j].y}\n")

    print("\nReplacing one full corner with set_corner():")
    ping_table.set_corner(2, img_point(550, 350))
    print(ping_table)

    print("\nReplacing full net position with set_net_position():")
    ping_table.set_net_position(0,img_point(320, 210))
    print(ping_table)


