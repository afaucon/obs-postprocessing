import argparse
import logging
import os
import os.path
import random
import re
import sys
import subprocess
import string


def validate_video(video_file_path):
    if not video_file_path.endswith('.mkv'):
        sys.exit('Error: Only .mkv video have currently been tested.')
    return video_file_path

def validate_dusting_rules(rules_file_path):
    dusting_rules = []
    last_timestamp = -1
    with open(rules_file_path, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith('#') or line == "":
                continue  # Possibility to have blank lines or commented lines
            regex = r"^((?:\d+[\:\.]){1,2}\d+)\s*\=\s*(.*)$"
            matches = re.findall(regex, line)
            if len(matches) != 1:
                sys.exit('Error: Format error in ' + rules_file_path + ' at line: ' + line)
            dusting_rules.append({'timestamp':matches[0][0],'value':matches[0][1]})

            # Check that timestamps are be monotonically increasing
            current_timestamp_splitted = [int(i) for i in dusting_rules[-1]['timestamp'].split(':')]
            if len(current_timestamp_splitted) == 2:
                current_timestamp_splitted.insert(0, '00')
            multiplicator = [3600, 60, 1]
            current_timestamp = 0
            for i in range(len(multiplicator)):
                current_timestamp += current_timestamp + current_timestamp_splitted[i] * multiplicator[i]
            if current_timestamp <= last_timestamp:
                sys.exit('Error: The timestamps must be monotonically increasing: ' + current_timestamp)
            last_timestamp = current_timestamp
    return dusting_rules

def get_chapters(dusting_rules):
    chapters = []
    for desc in dusting_rules:
        if desc['value'].lower() != 'cut':
            chapters.append({'timestamp':desc['timestamp'],'title':desc['value']})
    return chapters

def get_periods_to_keep(dusting_rules):
    periods_to_keep = []
    a_sequence_is_ongoing = False
    for desc in dusting_rules:
        if desc['value'].lower() == 'cut':
            if a_sequence_is_ongoing:
                periods_to_keep[-1].append(desc['timestamp'])
                a_sequence_is_ongoing = False
        else:
            if not a_sequence_is_ongoing:
                periods_to_keep.append([desc['timestamp']])
                a_sequence_is_ongoing = True
    return periods_to_keep

def periods_to_keep_as_string(periods_to_keep):
    periods_to_keep_as_str = ""
    for period in periods_to_keep:
        start = period.pop(0)
        if start != "00:00:00":
            periods_to_keep_as_str += start
        periods_to_keep_as_str += '-'
        try:
            stop = period.pop()
            periods_to_keep_as_str += stop
        except IndexError:  # No stop
            pass
        periods_to_keep_as_str += ',+'
    periods_to_keep_as_str = periods_to_keep_as_str[:-2]
    return periods_to_keep_as_str

def create_command(video_file_path, chapters_filename, periods_to_keep):
    command = [ 'mkvmerge' ]

    if os.path.exists(chapters_filename):
        chapters_options = [
            '--chapters',
            chapters_filename
        ]
        command.append(chapters_options)

    if len(periods_to_keep) > 0:
        split_options = [
            '--split',
            'parts:' + periods_to_keep_as_string(periods_to_keep)
        ]
        command.append(split_options)

    # Compute output file name based on the input file name
    output_filename = ''.join(video_file_path.split('.')[:-1]) + '-postprocessing' + '.' + video_file_path.split('.')[-1]
    output_options = [
        '-o',
        output_filename
    ]
    command.append(output_options)

    arguments = [ video_file_path ]
    command.append(arguments)

    # If there is nothing to do, return none
    if '--chapters' not in command and '--split' not in command:
        command = None

    return command

def main(video_file_path, rules_file_path, dry_run):
    video = validate_video(video_file_path)
    dusting_rules = validate_dusting_rules(rules_file_path)

    # Computing the chapters
    chapters = get_chapters(dusting_rules)
    logging.info(chapters)

    # Write chapters to a temporary file
    chapters_filename_length = 16
    chapters_filename = 'zz' + ''.join(random.choice(string.ascii_lowercase) for i in range(chapters_filename_length))
    if len(chapters) > 0:
        with open(chapters_filename, 'w') as f:
            for i in range(len(chapters)):
                chapter = chapters[i]
                f.write('CHAPTER' + f"{i:02d}" + '=' + chapter['timestamp'] + '.000' + '\n')
                f.write('CHAPTER' + f"{i:02d}" + 'NAME' + '=' + chapter['title'] + '\n')

    # Computing the periods to keep
    periods_to_keep = get_periods_to_keep(dusting_rules)
    logging.info(periods_to_keep)

    # Creating the command to run
    # Example:
    #   command = "mkvmerge --chapters dev/chapters.d --split parts:00:00:06-00:00:16,+00:00:26-00:00:36 -o toto.mkv dev/2023-05-12_13-50-15.mkv"
    command = create_command(video_file_path, chapters_filename, periods_to_keep)

    if command is None:
        sys.exit('Error: No rules to apply')
    else:
        logging.info('Running: ' + ' '.join(command))
        if dry_run:
            logging.info('Command not executed as in dry-run mode')
        else:
            subprocess.run(command)

    # Remove the chapters temporary file
    if os.path.exists(chapters_filename):
        os.remove(chapters_filename)

if __name__ == '__main__':

    parser = argparse.ArgumentParser(
                    prog='Viddusting',
                    description='Allows to cut sequences and create chapters in a video from a simple description as file')

    parser.add_argument('-v', '--verbose',
                        action='store_true')
    parser.add_argument('--dry-run',
                        action='store_true')
    parser.add_argument('-r', '--rules')
    parser.add_argument('video_file_path')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.basicConfig(level=logging.INFO)

    video_file_path = args.video_file_path
    if not os.path.exists(args.video_file_path):
        sys.exit('Error: Video not found: ' + video_file_path)

    rules_file_path = args.rules
    if rules_file_path is None:
        # If dusting_rules is not provided, assumption is made from the video base name + '.vdr' 
        rules_file_path = '.'.join(video_file_path.split('.')[:-1]) + '.vdr'
    if not os.path.exists(rules_file_path):
        sys.exit('Error: Dusting rules not found: ' + rules_file_path)

    # Run the main process
    main(video_file_path, rules_file_path, args.dry_run)