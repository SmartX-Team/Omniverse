"""slice_of_life_adjustments

This file only contains elements that could be left away, but they are way of uniqifing the project.
"""
def print_fox() -> None:
    # https://www.asciiart.eu/image-to-ascii - website used to create the picture
    print("""....................................................................................................
....................................................................................................
....................................................................................................
....................................................................................................
....................................................................................................
....................................................................................................
....................................................................................................
....................................................................................................
...........................................:-==+****+==-:...........................................
........................................-#+==============+*=........................................
....................................-#@#+===================#@#=:...................................
.................................-#@@@*======================+%@@%=.................................
...............................-@@@@@+========================+%@@@@=...............................
.............................+%@@@#**==========================+#*@@@@*:............................
..........................:%@@@@%-=*=====#%++#*=+**+=+#++#%+====**-#@@@@@-..........................
........................#@@@@*=..:*==+++==-:....=#%+...::--=+++++#-..-*%@@@#:.......................
.......................:@@%**....-*=---:....................-=-..=+.....*@@@=.......................
........................:*@%*-=:.=-..............................=+.-#@@@@#-........................
...........................=%@@@@%#.............................-*@%@@@@+...........................
..............................:+#%%#:..........................-#@%#*-..............................
....................................=+.......................:++....................................
......................................**:..................:*%......................................
......................................*+=:................:-+#......................................
......................................#=:...................-#......................................
......................................#-....................-*-.....................................
.....................................=*=-...................=++.....................................
.....................................*==-..................-==*:....................................
....................................-+==-..................===+=....................................
....................................=+===.:..............::===++....................................
...................................+*++====:.............====++**...................................
.................................-+=++======-::.......::-+==+++*++=.................................
................................++==++====++====....===++++++++*+++*................................
...............................++=+=+*=++++++++++..-++++++++++**++++*...............................
..............................-+==+++*+++++++++%#-:*++*%*++*++#*+++++=..............................
..............................++++++++#++++#++#@@#*@#@@@%#@*+%#*+++++*..............................
..............................*++++++++%%##%@%@@@@@@@@@@@@@@@**++++++#..............................
............................:##++++++++*%@@@@@@@@@@@%#=:...:=#%%*++++*..............................
...........................=*+***+++++++*@@@@@@@#*+++=---:.......-+##+..............................
..........................+*+++*#********#@@@*+++++++++++=...........=%:............................
.........................-*++++++*########+++++++++++++++=:............-+:..........................
.........................+*+++++++++++++++++++++++++++=:.................*-.........................
.........................**+++++++++++++++++++++++++++-::::...............+-........................
.........................+**++++++++++++++++++++++++++++++=-------:.......:+........................
.........................=#***+++++++++++++++++++++*******+-----------:....*........................
..........................%******++++++++++++************=--------------:..*........................
..........................:#****************************=+*+##+-....:+#*=-:+........................
...........................:*#************************##*=:.............+*=-........................
..............................*#******************#%*:...................-*.........................
.................................=+*#########*+=:...................................................
....................................................................................................
....................................................................................................
....................................................................................................
.........................................................................................NIKI.......
....................................................................................................
....................................................................................................""")
    
def print_info() -> None:
    print("""
# =======================================================================================
#  |  _   _  ___         _  __ ___   _____  _____  ____   _____   ____    ___   ____   |
#  | | \ | ||_ _|       | |/ /|_ _| |_   _|| ____|/ ___| |_   _| |  _ \  / _ \ / ___|  |
#  | |  \| | | |  _____ | ' /  | |    | |  |  _|  \___ \   | |   | |_) || | | |\___ \  |
#  | | |\  | | | |_____|| . \  | |    | |  | |___  ___) |  | |   |  _ < | |_| | ___) | |
#  | |_| \_||___|       |_|\_\|___|   |_|  |_____||____/   |_|   |_| \_\ \___/ |____/  |
#  |                                                                                   |
#  |  Written by Niki C. Zils for the Gwangju Institute of Science and Technology (1)  |
#  | - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - |
#  | This extension is exclusivly written for Clearpath's UGV Husky (2) with the       |
#  | intention of it being used in combination with Nvidia's Isaac Sim (3) and ROS2    |
#  | Humble (4).                                                                       |
# ========================================================================================

# Links:
# (1) https://ewww.gist.ac.kr/en/main.html
# (2) https://clearpathrobotics.com/husky-unmanned-ground-vehicle-robot/
# (3) https://docs.omniverse.nvidia.com/isaacsim/latest/overview.html
# (4) https://docs.ros.org/en/humble/index.html
""")

def print_instructions_for_tank_controll() -> None:
    print("""
# How to read the display
#  __     __
# |  |   |  |   ^ Anything above denotes a positive (+) velocity
# |  |   |  |   |
# |██|   |██|  <- The dots start out here - They show the current speed of the left and right side
# |  |   |  |   |
# |__|   |__|   V Anything below means a negative (-) velocity
#
#
# How it works
# As the main input source you use your mouse. (represented by this triangle: ▲)
# 
#  ____((______                                __     __
# |    _\\     |  With a left click the left  |  |   |  |
# |   |█|_|    |  wheel speed is determined.  |██| ▲ |  |
# |   |   |    |                              |  |   |██|
# |   |___|    |  Where as the right speed    |  |   |  |
# |____________|  stays untouched.            |__|   |__|
# 
# 
#  ____((______                                __     __
# |    _\\     |  With a right click the      |  |   |  |
# |   |_|█|    |  rigth wheel speed is        |██|   |  |
# |   |   |    |  determined.                 |  |   |  |
# |   |___|    |  Where as the left speed     |  |   |  |
# |____________|  stays untouched.            |__| ▲ |██|
# 
# 
#  ____((______                                __     __
# |    _\\     |  With a middle click the     |██| ▲ |██|
# |   |_█_|    |  speed on both sides gets    |  |   |  |
# |   |   |    |  changed to the same         |  |   |  |
# |   |___|    |  level.                      |  |   |  |
# |____________|                              |__|   |__|
# 
# It's important to note that this controller won't send any signal until both sides have been changed at least once.
# 
""")