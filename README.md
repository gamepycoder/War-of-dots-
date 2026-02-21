WAR OF DOTS
=====

War of Dots is a LAN RTS war game, a simple barebones war simulation built in python with pygame. Original credit goes to https://warofdots.net/


Feel free to start issues, I will see and will fix (or at least respond).
Feel free to contribute on the suggestion branch.

TODO
====
I want to get short term stuff done before doing my next code review and long term is what the code review is to help archive.

Short term:
----

 - Add stats dictionary to the info that's sent to client (e.g. {"cities owned":[_number of cities owned for each player_], "troops owned":[_number of troops owned for each player_], "total damage":[_total damage dealt this server frame for each player_], "current winner":_current winner_} ect)
 - Add stats dictionary to the troop info that's sent to client (e.g. {"terrain on":_terrain on_, "number of attackers":_number of attackers (enemies in range)_, "attacking dir":[_attacking dir (xy to dir dist on the offset of closest[0])_]} ect)
 - Add stats dictionary to the city info that's sent to client (e.g. {"timer":_timer_, "timer target":_timer target_, "produced":[_produced so far_]} ect)
 - Add win condition and make it so client reads "current winner" constantly to present that info at the end of the game


Long term:
----

 - playtest and refine constants
 - add strategy info
 - use numpy better for performance
 - make code more robust to internet issues
 - add map making
 - ability to save seed + city layout
 - saving and loading game state
 - more visual stuff?

Suggestions (just edit to add suggestions, I'll put them in long or short term):
---


INSTRUCTIONS TO PLAY:
=====================
 - start server and enter number of players
 - enter port, just enter 0, use other numbers when you think other people are playing the game on the same lan/router/network
 - should say waiting for players, will connect with first `PLAYERS` (number of players you entered) number of clients
 - start the clients
 - on each client type in the ip address then the port number you typed in the server (e.g. '0')
 - start playing when the pygame window pops up by pressing `p` to unpause, have fun!

Controls
======

Left Click: Grab a unit and draw a line to show it where to go. Release to save the path.

Right Click: Drag the mouse to move your view across the map.

Scroll Wheel: Zoom in and out on the spot where your mouse is pointing.

Spacebar: Send all your saved moves to the server.

C: Delete the paths you drew before you send them.

P: Send pause request.

Terminal: Use the terminal to set the IP/PORT address and restart the client.

Code description
=======

Server-Side Logic
------

Connections: Every player has their own dedicated connection to the server.

Game Speed: The server processes the game state at 45 FPS.

World Generation:

 - Terrain: Uses math functions to create natural-looking landmasses that always form an island shape.

 - Forests: Forests are placed automatically based on height, ensuring they only appear on plains.

 - City Placement: Cities are spread out randomly but follow rules to make sure they aren't too close to each other or the edge of the map.

Terrain Types & Modifiers:

 - Plains: Standard ground. (100% attack power, 100% movement speed).

 - Hills: High ground advantage. (150% attack power, 70% movement speed). Vision buff.

 - Forests: Dense cover. (75% attack power, 80% movement speed). Vision debuff.

 - Water: High vulnerability. (50% attack power, 60% movement speed).

 - Mountains: Impassable. These act as walls that units cannot cross.

Vision & Territory:

 - Fog of War: The server only sends you information about enemy units if your own units can actually see them.

 - Borders: The game tracks which parts of the map you own based on where your units walk and which cities you control.

Mechanics:

 - Movement: Units follow the lines you draw but will avoid bumping into teammates.

 - Combat: Units fight automatically when enemies get close. Units on Hills deal significantly more damage than those in Water or Forests.

 - Supply System: Units heal when they are near friendly cities. If they go too far into enemy land, their health will regenerate slower or start to drop.

 - City Logic: You capture cities by standing inside them. Cities create new units over time, slowing down if your army is already very large.

Client-Side Rendering
-------

Performance: The visual display updates 30 times per second.

Terrain Visuals: Uses a special smoothing method to turn the square map grid into curved, natural-looking coastlines and hills.

Drawing: The game draws the map in layers: first the ground, then the units, and finally the fog and border lines.

Camera: Includes 10 different zoom levels to let you see the whole map or close-up action.