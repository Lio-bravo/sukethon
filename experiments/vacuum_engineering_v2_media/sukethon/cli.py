import argparse
import json
from pathlib import Path

from .ros_monitor import collect, validate_config
from .telemetry import analyze, load_samples


def main(argv=None):
    parser = argparse.ArgumentParser(description="Box stacking task and observation tools")
    sub = parser.add_subparsers(dest="command", required=True)
    collect_parser = sub.add_parser("collect", help="record approved JointState observations")
    collect_parser.add_argument("--config", default="config/monitor.json")
    collect_parser.add_argument("--output", required=True)
    analyze_parser = sub.add_parser("analyze", help="analyze a JSONL recording")
    analyze_parser.add_argument("recording")
    analyze_parser.add_argument("--command-max-age", type=float, default=0.5)
    analyze_parser.add_argument("--output")
    dry = sub.add_parser("dry-run", help="synthetic logic exercise, not physics validation")
    dry.add_argument("--config", default="config/task.json")
    dry.add_argument("--a-count", type=int, default=4)
    dry.add_argument("--fail", choices=["grasp", "lift", "transfer", "place"])
    dry.add_argument("--placement-offset", type=float, default=0.0)
    args = parser.parse_args(argv)
    if args.command == "dry-run":
        from .task import load_layout, Pose
        from .supervisor import Detection, DryRunAdapter, Supervisor
        try:
            pallet, count = load_layout(json.loads(Path(args.config).read_text(encoding="utf-8")))
            if not 0 <= args.a_count <= count or args.a_count > 8 or count - args.a_count > 8:
                raise ValueError("Class counts must fit the configured task and zone capacities")
            boxes = [Detection("box-{:02d}".format(i), "A" if i < args.a_count else "B",
                               Pose(0.5, 0, 0.9), 1.0) for i in range(count)]
            robot = DryRunAdapter(boxes, {args.fail: 1} if args.fail else {}, args.placement_offset)
            result = Supervisor(pallet, robot, expected_boxes=count).run()
            result["validation_scope"] = "synthetic_logic_only"
            print(json.dumps(result, indent=2))
            return 0 if result["status"] == "complete" else 2
        except (ValueError, KeyError, TypeError, OSError) as exc:
            parser.error(str(exc))
    elif args.command == "collect":
        config = json.loads(Path(args.config).read_text(encoding="utf-8"))
        print(json.dumps(collect(config, args.output), ensure_ascii=False, indent=2))
    else:
        result = analyze(load_samples(args.recording), args.command_max_age)
        text = json.dumps(result, ensure_ascii=False, indent=2)
        if args.output:
            Path(args.output).write_text(text + "\n", encoding="utf-8", newline="\n")
        else:
            print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
