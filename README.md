# Video dusting

The goal of this project is, from a single file that describes a meeting video recording (i.e. timestamps list of chapters and cut sequences), to run a post processing of the video recording, in a single command, that produces the resulting videos with cut sequences and chapters in it.

## Requirements

- Python 3.6 at minimum because f-strings format are used. Not tested if more restrictions.
- External tools: mkvmerge from mkvtoolnix
- Tested with:
    - Ubuntu 2.04.2 LTS
    - mkvmerge v65.0.0
    - mkv files

### Installation

- Clone the source repository.
- Create a `viddusting` file in a folder that is configured in your `$PATH` environment variable with: 

```bash
#!/bin/bash

python3 ~/path/to/your/cloned/repo/main.py "$@"
```

- Make the file executable.

## Usage

Refer to `viddusting --help`.

- In short, with implicit dusting rules:

```
viddusting myvideo.mkv
```

*Note: To use implicit dusting rules, a dusting rules file must exist with the same name as the video file, but with '.vdr' as extension.*

- With explicit dusting rules:

```
viddusting -r dusting-rules myvideo.mkv
```

## Limitations

- Only mkv files have been tested
- mkv files must have a keyframe interval of at most 1s

## Fortmat of dusting rules file

Rules:
- The format of each line must be : timestamp = data
- timestamp must be: hh:mm:ss  or  mm:ss
- data must be: cut  or  a chapter title
- The timestamps must be monotonically increasing. 

By default, the output file will be cut from the beginning, 
i.e. it is not needed to write as first instruction: 00:00:00 = Cut

Example 1:

```
00:00:00 = Introduction
00:00:06 = From 0s to 5s
00:00:11 = From 5s to 10s
00:00:16 = cut
00:00:26 = From 20s to 25s
00:00:31 = Cut
00:00:36 = From 30s until the end
```

Example 2:

```
00:01:04 = Introduction of the training
00:02:36 = cut
00:03:44 = Chapter 1 of the training
00:13:14 = Chapter 2 of the training
00:17:01 = cut
00:25:16 = Chapter 3 of the training
00:29:26 = Conclusion of the training
00:31:51 = cut
```