"""HonestAngle command line: init, verify, report. Stdlib only."""
import argparse
import json
import sys

from .receipt import create_receipt, load_receipt, receipt_intact, write_receipt
from .verify import changed_rects, result_json, verify_image


def cmd_init(args):
    receipt = create_receipt(args.image, block_size=args.block, note=args.note or "")
    write_receipt(receipt, args.out)
    print("receipt written: %s" % args.out)
    print("  image sha256 : %s" % receipt["image_sha256"])
    print("  merkle root  : %s" % receipt["merkle_root"])
    print("  blocks       : %d (%dpx)" % (receipt["block_count"], receipt["block_size"]))
    return 0


def cmd_verify(args):
    receipt = load_receipt(args.receipt)
    intact = receipt_intact(receipt)
    result = verify_image(args.image, receipt, receipt_was_intact=intact)
    if args.json_out:
        result["receipt_sha256"] = receipt.get("receipt_sha256", "")
        result["image_sha256_receipt"] = receipt.get("image_sha256", "")
        result_json(result, args.json_out)
    print("verdict        : %s" % result["verdict"])
    if result.get("reason"):
        print("reason         : %s" % result["reason"])
    if result.get("localized"):
        print("blocks matched : %d / %d" % (result["blocks_matched"], result["blocks_total"]))
        print("blocks changed : %d (tamper ratio %.4f)" % (result["blocks_changed"], result["tamper_ratio"]))
        rects = changed_rects(result)
        for x, y, w, h in rects[:args.max_rects]:
            print("  changed block at x=%d y=%d w=%d h=%d" % (x, y, w, h))
        if len(rects) > args.max_rects:
            print("  ... and %d more" % (len(rects) - args.max_rects))
    elif result["verdict"] in ("VERIFIED", "CHANGED"):
        print("root now       : %s" % result.get("root_now", ""))
        print("root receipt   : %s" % result.get("root_receipt", ""))
    if not intact:
        return 2
    return 0 if result["verdict"] == "VERIFIED" else 1


def main(argv=None):
    p = argparse.ArgumentParser(prog="honestangle", description="Cryptographic pixel provenance for ComfyUI outputs")
    sub = p.add_subparsers(dest="cmd", required=True)
    pi = sub.add_parser("init", help="create a receipt for an image")
    pi.add_argument("image")
    pi.add_argument("-o", "--out", default="receipt.json")
    pi.add_argument("--block", type=int, default=16)
    pi.add_argument("--note", default="")
    pi.set_defaults(func=cmd_init)
    pv = sub.add_parser("verify", help="verify an image against a receipt")
    pv.add_argument("image")
    pv.add_argument("--receipt", required=True)
    pv.add_argument("--json-out", default=None, help="write full block results as JSON")
    pv.add_argument("--max-rects", type=int, default=20)
    pv.set_defaults(func=cmd_verify)
    ns = p.parse_args(argv)
    return ns.func(ns)


if __name__ == "__main__":
    sys.exit(main())
