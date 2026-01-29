#!/usr/bin/env python3
from segments import SegmentsClient


def main() -> None:
    methods = [m for m in dir(SegmentsClient) if "delete" in m.lower()]
    print("\n".join(methods))


if __name__ == "__main__":
    main()
