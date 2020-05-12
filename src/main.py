#!/usr/bin/env python3
"""

To easily test this project without running it on multiple devices,
first make sure you have ipython version >= 7.
Then start this script by `./src/main.py` or `python3 src/main.py`
Then in another terminal start `ipython3` inside the src/ directory.
```
from main import *
await connect()
```
This is possible due to the use of a lazy proxy to load all hardware elements.
See src/peripherals.py for more info.
"""
import json
import uuid
import asyncio
import random
import time
import sys
import traceback
from enum import Enum

# The paho client is awfully stupid and eats all exceptions in its callbacks
# See https://github.com/eclipse/paho.mqtt.python/issues/365 for info.
# Therefore we use gmqtt instead so we can do exception handling ourselves
# It also allows us to use asyncio
from gmqtt import Client as MQTTClient

import peripherals
import oled


class State(Enum):
    Discover = 0
    Leader = 1
    Guesser = 2


# The three states we can be in when discovering
class DiscoverState(Enum):
    Unknown = 0
    Host = 1
    Client = 2


# The base topic to send and receive on
BASE_TOPIC = 'BAAA-ITTek/2020/1st-semester/project2/group3/'

# Unique client id for this session
UUID = str(uuid.uuid4())

# Our MQTT client, initialized with our uuid
client = MQTTClient(client_id=UUID)

# Current global state
state = State.Discover

# Current discover state
discover_state = DiscoverState.Unknown
# Player uuids we know of incl. ourselves
player_uuids = [UUID]

# State.Leader variables
correct_number = 0
guesses = {}


def on_connect(client, flags, rc, properties):
    print('Connected with result code ' + str(rc))

    # Use no_local=True so we don't get our own messages
    # This requires a fairly recent MQTT broker though
    client.subscribe(BASE_TOPIC + '#', no_local=True)


async def on_message(client, topic, payload, qos, properties):
    # We will use these later
    global state, discover_state, player_uuids
    # Get the topic excluding the BASE_TOPIC
    topic = topic[len(BASE_TOPIC):]
    # Also decode the json payload
    payload = json.loads(payload)

    # Ignore our own messages in case the no_local=True when subbing failed
    if payload['uuid'] == UUID:
        return

    # If we got some roles then the game is starting
    if topic == 'game/roles':
        await start_round(payload)

    # If the game is ongoing and we're the leader
    if state == State.Leader:
        if topic == 'game/guess':
            guesses[payload['uuid']] = payload['guess']
            print("guesses:", guesses)
            if len(guesses) == len(player_uuids) - 1:
                # TODO: figure out who won and sleep a bit (or require button push) to continue
                # Start a new round
                if discover_state == DiscoverState.Host:
                    await new_round()
                else:
                    client.publish(BASE_TOPIC + 'game/new_round', payload=True)

    # If we are the host
    if discover_state == DiscoverState.Host:
        # Start a new round when we are asked to
        if topic == 'game/new_round':
            new_round()

    # Only if we're still discovering
    # TODO: Allow players to join while the game is ongoing
    if state == State.Discover:
        # If we are the host and we get a find request
        if topic == 'discover/find' and (
                discover_state == DiscoverState.Unknown
                or discover_state == DiscoverState.Host):
            discover_state = DiscoverState.Host
            # Add it's uuid to our list if not already there
            if payload['uuid'] not in player_uuids:
                player_uuids.append(payload['uuid'])
            print("players:", player_uuids)
            # And send an acknowledgement
            client.publish(BASE_TOPIC + 'discover/ack',
                           payload=dict(uuid=UUID, player_uuids=player_uuids))
            oled.show_msg(f'You are the host (player 1).\n'
                          f'Current players: {len(player_uuids)}.\n'
                          f'Press button to start the game.')
            peripherals.led_key.segments[0] = f'PLAYER 1'
        elif topic == 'discover/ack' and (
                discover_state == DiscoverState.Unknown
                or discover_state == DiscoverState.Client):
            discover_state = DiscoverState.Client
            # Update our uuids
            player_uuids = payload['player_uuids']
            print("players:", player_uuids)
            # Display a message to the user
            player = player_uuids.index(UUID) + 1
            oled.show_msg(f'You are player {player}.\n'
                          f'Waiting for host to start the game.\n'
                          f'Current players: {len(player_uuids)}')
            peripherals.led_key.segments[0] = f'PLAYER {player}'

    # When on_message is async we need a return value
    return 0


async def start_round(roles):
    global state, correct_number, guesses
    guesses = {}
    if roles['leader'] == UUID:
        state = State.Leader
    else:
        state = State.Guesser

    msg = ''
    if state == State.Leader:
        msg = 'Choose number that the other players will try to guess.'

    elif state == State.Guesser:
        leader_player = player_uuids.index(roles["leader"]) + 1
        msg = (f'Player {leader_player} is choosing a number.\n'
               f'Enter your guess.')

    oled.show_msg(msg)

    columns = [0, 0, 0, 0, 0, 0, 0, 0]
    prev_switches = [
        [False, 0],
        [False, 0],
        [False, 0],
        [False, 0],
        [False, 0],
        [False, 0],
        [False, 0],
        [False, 0],
    ]

    # Loop for 25 sec
    total_time = 25
    end_time = time.time() + total_time
    while True:
        current_time = time.time()
        remaining_time = end_time - current_time
        oled.show_msg(msg + f'\nYou have {(remaining_time+1):.0f} sec.',
                      dbg=False)

        # For each led
        for i in range(8):
            # Turn it on/off depending on remaining time
            peripherals.led_key.leds[i] = i < (remaining_time / total_time) * 8

        # For each switch/segment
        for i in range(8):
            # Display the current number
            peripherals.led_key.segments[i] = str(columns[i])

            # Get the value
            val = peripherals.led_key.switches[i]
            # Get the previous value and last time it was pressed
            prev_val, prev_time = prev_switches[i]
            # If it is held down and wasn't before or we've been holding it for 0.3 sec
            if val and (not prev_val or current_time > prev_time + 0.3):
                # Increase number in that position
                columns[i] = (columns[i] + 1) % 10
                # Update the last pressed time
                prev_switches[i][1] = current_time
            # Update the prev value
            prev_switches[i][0] = val

        await asyncio.sleep(0.01)
        if current_time > end_time:
            break

    # Construct number from the place values
    number = 0
    for i in range(8):
        number += columns[i] * 10**i

    print("Entered number:", number)

    if state == State.Leader:
        correct_number = number
        oled.show_msg('Waiting for other players.')
    elif state == State.Guesser:
        client.publish(BASE_TOPIC + 'game/guess',
                       payload=dict(uuid=UUID, guess=number))
        oled.show_msg('Waiting for result.')


async def button_pressed():
    """Function called when the main button is pressed"""
    print("Button pressed")
    global state
    if state == State.Discover:
        if discover_state == DiscoverState.Unknown:
            oled.show_msg('Looking for other players.\n'
                          'No other players found - cannot start game.')
        elif discover_state == DiscoverState.Host:
            if len(player_uuids) < 2:
                print('No other players found.')
                return
            await new_round()
        elif discover_state == DiscoverState.Client:
            # Ignore the button press if client
            pass


async def new_round():
    """Host only function to start a new round."""
    # Choose a leader for this round
    # TODO: remove this debug statement
    #leader = random.choice(player_uuids)
    leader = player_uuids[0]
    # The guessers are player_uuid but without the leader aka. the rest of the players
    guessers = list(set(player_uuids) - {leader})

    roles = dict(leader=leader, guessers=guessers)

    client.publish(BASE_TOPIC + 'game/roles', payload=roles)

    oled.show_msg('Starting game.', big=True)

    await start_round(roles)


async def connect():
    """Connect to mqtt server, and send discover/find."""
    # Connect to the mqtt server using default port
    await client.connect('mqtt.eclipse.org')

    # Look for other players
    client.publish(BASE_TOPIC + 'discover/find', payload=dict(uuid=UUID))


async def main():
    # Setup event handlers
    client.on_connect = on_connect
    client.on_message = on_message

    await connect()

    oled.show_msg('Looking for other players.', big=True)

    peripherals.led_key.segments[0] = f'SCANNING'

    button_was_pressed = False

    # Run forever
    # TODO: Provide some other way than CTRL-C to exit?
    while True:
        if peripherals.button.value and not button_was_pressed:
            await button_pressed()
        button_was_pressed = peripherals.button.value

        await asyncio.sleep(0.1)


async def shutdown(loop):
    """Shutdowns the program as gracefully as possible."""
    # Make sure we always disconnect from the mqtt broker
    await client.disconnect()

    # And clear the displays
    oled.clear()
    peripherals.led_key.segments[0] = ' ' * 8
    for i in range(8):
        peripherals.led_key.leds[i] = False

    # Make sure we're completely done with async stuff
    # See https://www.roguelynn.com/words/asyncio-exception-handling/
    # Gather tasks
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]

    # Cancel them
    for task in tasks:
        task.cancel()
    # Wait for them to finish up
    await asyncio.gather(*tasks, return_exceptions=True)

    # Then shutdown the event loop
    loop.stop()


def handle_exception(loop, context):
    print(context.get('message', 'Unhandled exception.'))
    # Print the exception with a proper traceback
    # This is hella hacky but somehow the best way i found to do it
    try:
        # Raise the exception that was caught
        # We need that since we aren't technically handling an exception
        # according to python so right here sys.exc_info() would be None
        raise context['exception']
    except Exception:
        # Then we catch that exception and get currrent exc data
        exc_type, exc_value, exc_traceback = sys.exc_info()
        # Then we print the exception with the traceback
        # Taking care to exclude this wrapper (using .tb_next)
        traceback.print_exception(exc_type, exc_value, exc_traceback.tb_next)
    # Then run shutdown logic
    loop.create_task(shutdown(loop))


if __name__ == '__main__':
    # qMQTT is async, so we need an event loop and to do
    # some magic to make it play nicely with gpiozero
    loop = asyncio.get_event_loop()

    loop.set_exception_handler(handle_exception)

    # Run main until CTRL-C
    try:
        loop.run_until_complete(main())
        # loop.run_forever()
    except KeyboardInterrupt:
        print("\nReceived exit, exiting...")
        loop.run_until_complete(shutdown(loop))
    except asyncio.CancelledError:
        # ignore
        pass
