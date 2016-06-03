#  -*- coding: utf-8 -*-
##    @package simulator.py
#      @author Matheus Portela & Guilherme N. Ramos (gnramos@unb.br)
#
# Adapts communication between controller and the Berkeley
# Pac-man simulator.

import argparse
import pickle
import random
import os

from berkeley.graphicsDisplay import PacmanGraphics as BerkeleyGraphics
from berkeley.layout import getLayout as get_berkeley_layout
from berkeley.pacman import runGames as run_berkeley_games
from berkeley.textDisplay import NullGraphics as BerkeleyNullGraphics, PacmanGraphics as BerkeleyTextGraphics

import messages
import agents


# Default settings (CLI parsing)
DEFAULT_LAYOUT = 'classic'
DEFAULT_NUMBER_OF_GHOSTS = 1


def log(msg):
    print '[  Adapter ] {}'.format(msg)


def __get_layout__(layout, num_ghosts):
    LAYOUT_PATH = 'layouts'
    file_name = str(num_ghosts) + 'Ghosts'
    layout_file = '/'.join([LAYOUT_PATH, layout, file_name])

    layout = get_berkeley_layout(layout_file)

    if not layout:
        raise ValueError("The layout " + layout_file + " cannot be found")

    log('Loaded {}.'.format(layout_file))

    return layout


def create_layout(layout_file):
    layout = get_berkeley_layout(layout_file)

    if layout is None:
        raise Exception("The layout " + layout_file + " cannot be found")

    log('Loaded {}.'.format(layout_file))

    return layout


def create_pacman(agent_class, port):
    pacman = agents.CommunicatingPacmanAgent(port=port)
    pacman.register_agent('pacman', agent_class)
    log('Created {} #{}.'.format(agent_class.__name__, pacman.agent_id))
    return pacman


def create_ghosts(num_ghosts, agent_class, port):
    ghosts = []

    for i in range(num_ghosts):
        ghost = agents.CommunicatingGhostAgent(i+1, port=port)
        ghost.register_agent('ghost', agent_class)
        log('Created {} #{}.'.format(agent_class.__name__, ghost.agent_id))
        ghosts.append(ghost)

    return ghosts


def create_display(display_type='None', zoom=1.0, frameTime=0.1):
    if display_type == 'Text':
        display = BerkeleyTextGraphics()
    elif display_type == 'Graphic':
        display = BerkeleyGraphics(zoom, frameTime=frameTime)
    elif display_type == 'None':
        display = BerkeleyNullGraphics()
    else:
        raise ValueError, 'Display type must be either Text, Graphic, or None'

    return display


def save_results(filename, results):
    with open(filename, 'w') as f:
        f.write(pickle.dumps(results))


def main():
    parser = argparse.ArgumentParser(description='Run Pacman adapter system.')
    parser.add_argument('-l', '--learn-num', dest='learn', type=int, default=100,
                       help='number of games to learn from')
    parser.add_argument('-t', '--test-num', dest='test', type=int, default=100,
                       help='number of games to test learned policy')
    parser.add_argument('-p', '--policy-file', dest='policy_filename', type=str,
                        help='load and save Pacman policy from the given file')
    parser.add_argument('-g', '--graphics', dest='graphics', action='store_true',
                        help='display graphical user interface')
    parser.add_argument('--no-graphics', dest='graphics', action='store_false',
                        help='do not display graphical user interface')
    parser.add_argument('--pacman-agent', dest='pacman_agent', type=str,
                        default='random', help='select pacman agent: random, ai, or eater')
    parser.add_argument('--ghost-agent', dest='ghost_agent', type=str,
                        default='ai', help='select ghost agent: random or ai')
    parser.add_argument('-o', '--output', dest='output_filename', type=str,
                        default='results.txt', help='results output file')
    parser.add_argument('--noise', dest='noise', type=int, default=0,
                        help='introduce noise in position measurements')
    parser.add_argument('--port', dest='port', type=int, default=5555,
                        help='TCP port to connect to controller')
    parser.set_defaults(graphics=False)
    parser.add_argument('--num-ghosts', dest='num_ghosts',
                        type=int, choices=xrange(1, 5),
                        default=DEFAULT_NUMBER_OF_GHOSTS,
                        help='number of ghosts in game')
    parser.add_argument('--layout', dest='layout', type=str,
                        default=DEFAULT_LAYOUT,
                        choices=['classic', 'medium'],
                        help='Game layout')

    args = parser.parse_args()

    agents.NOISE = args.noise

    learn_games = args.learn
    test_games = args.test
    policy_filename = args.policy_filename
    results_output_filename = args.output_filename
    policies = {}
    record = False

    if args.pacman_agent == 'random':
        pacman_class = agents.RandomPacmanAgent
    elif args.pacman_agent == 'ai':
        pacman_class = agents.BehaviorLearningPacmanAgent
    elif args.pacman_agent == 'eater':
        pacman_class = agents.EaterPacmanAgent
    else:
        raise ValueError, 'Pacman agent must be random, ai, or eater'

    if args.ghost_agent == 'random':
        ghost_class = agents.RandomGhostAgent
    elif args.ghost_agent == 'ai':
        ghost_class = agents.BehaviorLearningGhostAgent
    else:
        raise ValueError, 'Ghost agent must be random or ai'

    if args.graphics:
        display_type = 'Graphic'
    else:
        display_type = 'None'

    layout = __get_layout__(args.layout, args.num_ghosts)
    map_width = layout.width
    map_height = layout.height

    display = create_display(display_type=display_type)

    results = {
        'learn_scores': [],
        'test_scores': [],
        'behavior_count': {}
    }

    pacman = create_pacman(pacman_class, args.port)
    ghosts = create_ghosts(args.num_ghosts, ghost_class, args.port)

    if pacman_class == agents.BehaviorLearningPacmanAgent:
        results['behavior_count'][pacman.agent_id] = {}

    if ghost_class == agents.BehaviorLearningGhostAgent:
        for ghost in ghosts:
            results['behavior_count'][ghost.agent_id] = {}

    # Load policies from file
    if policy_filename and os.path.isfile(policy_filename):
        log('Loading policies from {}.'.format(policy_filename))
        with open(policy_filename) as f:
            policies = pickle.loads(f.read())

    # Initialize agents
    pacman.init_agent()
    for ghost in ghosts:
        ghost.init_agent()

    for i in range(learn_games + test_games):
        if i >= learn_games:
            log('TEST Game {} (of {})'.format(i+1-learn_games, test_games))
        else:
            log('LEARN Game {} (of {})'.format(i+1, learn_games))

        # Start new game
        pacman.start_game(map_width, map_height)
        for ghost in ghosts:
            ghost.start_game(map_width, map_height)

        # Load policies to agents
        if policy_filename and os.path.isfile(policy_filename):
            if pacman.agent_id in policies:
                log('Loading {} #{} policy.'.format(type(pacman).__name__,
                                            pacman.agent_id))
                pacman.send_message(messages.PolicyMessage(
                    agent_id=pacman.agent_id,
                    policy=policies[pacman.agent_id]))
                pacman.receive_message()


            for ghost in ghosts:
                if ghost.agent_id in policies:
                    log('Loading {} #{} policy.'.format(type(ghost).__name__,
                                            ghost.agent_id))
                    ghost.send_message(messages.PolicyMessage(
                        agent_id=ghost.agent_id,
                        policy=policies[ghost.agent_id]))
                    ghost.receive_message()

        if i >= learn_games:
            pacman.enable_test_mode()

            for ghost in ghosts:
                ghost.enable_test_mode()

        games = run_berkeley_games(layout, pacman, ghosts, display, 1, record)

        # Do this so as agents can receive the last reward
        pacman.send_message(pacman.create_state_message(games[0].state))
        pacman.receive_message()

        for ghost in ghosts:
            ghost.send_message(ghost.create_state_message(games[0].state))
            ghost.receive_message()

        # Log behavior count
        if pacman_class == agents.BehaviorLearningPacmanAgent:
            msg = messages.RequestBehaviorCountMessage(agent_id=pacman.agent_id)
            pacman.send_message(msg)
            behavior_count_msg = pacman.receive_message()
            log('{} behavior count: {}.'.format(type(pacman).__name__,
                                            behavior_count_msg.count))
            for behavior, count in behavior_count_msg.count.items():
                if behavior not in results['behavior_count'][pacman.agent_id]:
                    results['behavior_count'][pacman.agent_id][behavior] = []
                results['behavior_count'][pacman.agent_id][behavior].append(count)

        if ghost_class == agents.BehaviorLearningGhostAgent:
            for ghost in ghosts:
                msg = messages.RequestBehaviorCountMessage(agent_id=ghost.agent_id)
                ghost.send_message(msg)
                behavior_count_msg = ghost.receive_message()
                log('{} behavior count: {}.'.format(type(ghost).__name__,
                                            behavior_count_msg.count))
                for behavior, count in behavior_count_msg.count.items():
                    if behavior not in results['behavior_count'][ghost.agent_id]:
                        results['behavior_count'][ghost.agent_id][behavior] = []
                    results['behavior_count'][ghost.agent_id][behavior].append(count)

        # Log score
        if i >= learn_games:
            results['test_scores'].append(games[0].state.getScore())
        else:
            results['learn_scores'].append(games[0].state.getScore())

    # Save policies
    if policy_filename:
        if pacman_class == agents.BehaviorLearningPacmanAgent:
            pacman.send_message(messages.RequestPolicyMessage(pacman.agent_id))
            msg = pacman.receive_message()
            policies[pacman.agent_id] = msg.policy

        if ghost_class == agents.BehaviorLearningGhostAgent:
            for ghost in ghosts:
                ghost.send_message(messages.RequestPolicyMessage(ghost.agent_id))
                msg = ghost.receive_message()
                policies[ghost.agent_id] = msg.policy

        with open(policy_filename, 'w') as f:
            f.write(pickle.dumps(policies))

    # Save results
    print 'Learn scores:', results['learn_scores']
    print 'Test scores:', results['test_scores']

    save_results(results_output_filename, results)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print '\n\nInterrupted execution\n'
