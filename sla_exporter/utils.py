import re

HOST_PATTERN = re.compile(r"^(?P<prefix>.*)\[(?P<start>\d+)-(?P<end>\d+)\](?P<suffix>.*)$")


def is_parttern(target):
    return '[' in target and ']' in target 


def expand_patterns(pattern):
    result = []
    matches = HOST_PATTERN.search(pattern)
    start, end = int(matches.group('start')), int(matches.group('end'))
    for i in range(start, end+1):
        result.append("{}{}{}".format(matches.group('prefix'), str(i), matches.group('suffix')))
    return result


if __name__ == "__main__":
    print(expand_patterns("dx-pipe-frog-ii[1-14]-online:22000"))
