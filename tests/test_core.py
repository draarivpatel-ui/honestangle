import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from honestangle.hashing import (block_bytes, block_grid, image_blocks,
                                 merkle_proof, merkle_root, sha256_hex,
                                 verify_proof_at)
from honestangle.pngio import PngError, read_png, write_png_file, _paeth
from honestangle.receipt import (canonical_json, create_receipt,
                                 receipt_intact, write_receipt, load_receipt)
from honestangle.scene import edit_region, gradient_scene, write_scene
from honestangle.verify import changed_rects, verify_image


class TempImg:
    def __init__(self, w=96, h=64, ch=3):
        self.dir = tempfile.mkdtemp()
        self.orig = os.path.join(self.dir, "orig.png")
        write_scene(self.orig, w, h, ch)
        self.w, self.h, self.ch = w, h, ch

    def variant(self, name, x0, y0, ww, hh):
        _, _, _, px = read_png(self.orig)
        edited = edit_region(px, self.w, self.h, self.ch, x0, y0, ww, hh)
        p = os.path.join(self.dir, name)
        write_png_file(p, self.w, self.h, self.ch, edited)
        return p


class TestPngIO(unittest.TestCase):
    def test_round_trip_rgb(self):
        t = TempImg(40, 30)
        w, h, ch, px = read_png(t.orig)
        out = os.path.join(t.dir, "rt.png")
        write_png_file(out, w, h, ch, px)
        w2, h2, ch2, px2 = read_png(out)
        self.assertEqual((w, h, ch, px), (w2, h2, ch2, px2))

    def test_round_trip_rgba(self):
        px = bytes(range(4 * 4 * 4))
        p = os.path.join(tempfile.mkdtemp(), "a.png")
        write_png_file(p, 4, 4, 4, px)
        w, h, ch, got = read_png(p)
        self.assertEqual((w, h, ch, got), (4, 4, 4, px))

    def test_rejects_non_png(self):
        p = os.path.join(tempfile.mkdtemp(), "x.png")
        open(p, "wb").write(b"not a png at all")
        with self.assertRaises(PngError):
            read_png(p)

    def test_rejects_bad_depth_message(self):
        # hand-craft an IHDR with depth 16
        import struct, zlib
        sig = b"\x89PNG\r\n\x1a\n"

        def chunk(t, b):
            return struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t + b) & 0xFFFFFFFF)
        ihdr = struct.pack(">IIBBBBB", 2, 2, 16, 2, 0, 0, 0)
        raw = b"\x00" + b"\x00\x00\x00" * 2
        data = sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
        p = os.path.join(tempfile.mkdtemp(), "d16.png")
        open(p, "wb").write(data)
        with self.assertRaises(PngError) as cm:
            read_png(p)
        self.assertIn("8-bit", str(cm.exception))

    def test_paeth_known_values(self):
        self.assertEqual(_paeth(0, 0, 0), 0)
        self.assertEqual(_paeth(10, 0, 0), 10)
        self.assertEqual(_paeth(0, 10, 0), 10)
        self.assertEqual(_paeth(10, 10, 0), 10)
        self.assertEqual(_paeth(5, 9, 7), 7)


class TestGrid(unittest.TestCase):
    def test_even_grid(self):
        g = list(block_grid(64, 32, 16))
        self.assertEqual(len(g), 8)
        first = g[0]
        self.assertEqual(first, (0, 0, 0, 0, 16, 16))

    def test_partial_edge_blocks(self):
        g = list(block_grid(70, 50, 16))
        rows = 4  # ceil(50/16)
        cols = 5  # ceil(70/16)
        self.assertEqual(len(g), rows * cols)
        last = g[-1]
        self.assertEqual(last[4], 70 - 64)  # w remainder
        self.assertEqual(last[5], 50 - 48)  # h remainder

    def test_block_size_positive(self):
        with self.assertRaises(ValueError):
            list(block_grid(10, 10, 0))

    def test_block_bytes_isolated(self):
        pixels = bytes(range(4 * 4 * 3))
        bb = block_bytes(pixels, 4, 3, 1, 1, 2, 2)
        # rows y=1..2, cols x=1..2, 3 channels each
        expect = (
            pixels[(1 * 4 + 1) * 3:(1 * 4 + 3) * 3] +
            pixels[(2 * 4 + 1) * 3:(2 * 4 + 3) * 3]
        )
        self.assertEqual(bb, expect)


class TestMerkle(unittest.TestCase):
    def leaves(self, n):
        t = TempImg(32, 32)
        _, ls = image_blocks(t.orig, 16)
        return ls[:n]

    def test_single_leaf_root(self):
        ls = self.leaves(1)
        self.assertEqual(merkle_root(ls), ls[0]["digest"])

    def test_two_leaf_root(self):
        import hashlib
        a, b = "aa" * 32, "bb" * 32
        root = merkle_root([{"digest": a}, {"digest": b}])
        expect = hashlib.sha256(bytes.fromhex(a) + bytes.fromhex(b)).hexdigest()
        self.assertEqual(root, expect)

    def test_odd_count_duplicates_last(self):
        import hashlib
        a, b, c = "01" * 32, "02" * 32, "03" * 32
        l1 = hashlib.sha256(bytes.fromhex(a) + bytes.fromhex(b)).digest()
        l2 = hashlib.sha256(bytes.fromhex(c) + bytes.fromhex(c)).digest()
        root = merkle_root([{"digest": a}, {"digest": b}, {"digest": c}])
        self.assertEqual(root, hashlib.sha256(l1 + l2).hexdigest())

    def test_proof_verifies(self):
        ls = self.leaves(7)
        root = merkle_root(ls)
        for i in range(len(ls)):
            proof = merkle_proof(ls, i)
            self.assertTrue(verify_proof_at(ls[i]["digest"], proof, root, i), "leaf %d" % i)

    def test_proof_rejects_wrong_leaf(self):
        ls = self.leaves(7)
        root = merkle_root(ls)
        proof = merkle_proof(ls, 3)
        self.assertFalse(verify_proof_at(ls[2]["digest"], proof, root, 3))

    def test_proof_rejects_wrong_root(self):
        ls = self.leaves(4)
        proof = merkle_proof(ls, 1)
        self.assertFalse(verify_proof_at(ls[1]["digest"], proof, "00" * 32, 1))

    def test_proof_index_out_of_range(self):
        ls = self.leaves(4)
        with self.assertRaises(IndexError):
            merkle_proof(ls, 99)

    def test_empty_leaves_raise(self):
        with self.assertRaises(ValueError):
            merkle_root([])


class TestReceipt(unittest.TestCase):
    def test_receipt_fields(self):
        t = TempImg(64, 64)
        r = create_receipt(t.orig, block_size=16)
        self.assertEqual(r["width"], 64)
        self.assertEqual(r["block_count"], 16)
        self.assertEqual(len(r["leaf_digests"]), 16)
        self.assertTrue(receipt_intact(r))

    def test_deterministic_core(self):
        t = TempImg(64, 64)
        r1 = create_receipt(t.orig, block_size=16)
        r2 = create_receipt(t.orig, block_size=16)
        for k in ("image_sha256", "merkle_root", "leaf_digests", "receipt_sha256"):
            self.assertEqual(r1[k], r2[k], k)

    def test_leaf_list_matches_root(self):
        t = TempImg(48, 48)
        r = create_receipt(t.orig, block_size=16)
        root = merkle_root([{"digest": d} for d in r["leaf_digests"]])
        self.assertEqual(root, r["merkle_root"])

    def test_tampered_receipt_detected(self):
        t = TempImg(64, 64)
        r = create_receipt(t.orig, block_size=16)
        r["merkle_root"] = "11" * 32
        self.assertFalse(receipt_intact(r))

    def test_canonical_json_stable(self):
        self.assertEqual(canonical_json({"b": 1, "a": 2}), '{"a":2,"b":1}')

    def test_write_load_roundtrip(self):
        t = TempImg(32, 32)
        r = create_receipt(t.orig, block_size=16)
        p = os.path.join(t.dir, "r.json")
        write_receipt(r, p)
        r2 = load_receipt(p)
        self.assertEqual(r, r2)


class TestVerify(unittest.TestCase):
    def test_identical_image_verifies(self):
        t = TempImg(64, 64)
        r = create_receipt(t.orig, block_size=16)
        res = verify_image(t.orig, r)
        self.assertEqual(res["verdict"], "VERIFIED")
        self.assertEqual(res["blocks_changed"], 0)
        self.assertEqual(res["tamper_ratio"], 0.0)

    def test_single_block_edit_localized(self):
        t = TempImg(64, 64)
        r = create_receipt(t.orig, block_size=16)
        edited = t.variant("e.png", 20, 20, 8, 8)  # touches exactly block (1,1)
        res = verify_image(edited, r)
        self.assertEqual(res["verdict"], "TAMPERED")
        self.assertEqual(res["blocks_changed"], 1)
        rects = changed_rects(res)
        self.assertEqual(len(rects), 1)
        x, y, w, h = rects[0]
        self.assertEqual((x, y), (16, 16))

    def test_edit_larger_region(self):
        t = TempImg(64, 64)
        r = create_receipt(t.orig, block_size=16)
        edited = t.variant("e.png", 0, 0, 33, 33)  # 3x3 blocks touched (33 spans into 4th? 0..33 -> cols 0,1,2)
        res = verify_image(edited, r)
        self.assertEqual(res["verdict"], "TAMPERED")
        self.assertEqual(res["blocks_changed"], 9)

    def test_full_regen_detected(self):
        t = TempImg(64, 64)
        r = create_receipt(t.orig, block_size=16)
        other = os.path.join(t.dir, "other.png")
        write_scene(other, 64, 64)
        # different scene bytes? gradient_scene is deterministic; force difference
        _, _, _, px = read_png(t.orig)
        write_png_file(other, 64, 64, 3, edit_region(px, 64, 64, 3, 0, 0, 64, 64))
        res = verify_image(other, r)
        self.assertEqual(res["verdict"], "REGENERATED")
        self.assertEqual(res["blocks_changed"], res["blocks_total"])

    def test_dimension_change(self):
        t1 = TempImg(64, 64)
        r = create_receipt(t1.orig, block_size=16)
        small = os.path.join(t1.dir, "s.png")
        write_scene(small, 32, 32)
        res = verify_image(small, r)
        self.assertEqual(res["verdict"], "DIMENSIONS_MISMATCH")

    def test_broken_receipt_refused(self):
        t = TempImg(64, 64)
        r = create_receipt(t.orig, block_size=16)
        r["leaf_digests"][0] = "ff" * 32
        res = verify_image(t.orig, r, receipt_was_intact=False)
        self.assertEqual(res["verdict"], "RECEIPT_INVALID")

    def test_forged_leaf_list_refused(self):
        t = TempImg(64, 64)
        r = create_receipt(t.orig, block_size=16)
        # swap two leaf digests: list no longer matches the committed root
        r["leaf_digests"][0], r["leaf_digests"][1] = r["leaf_digests"][1], r["leaf_digests"][0]
        res = verify_image(t.orig, r)  # integrity flag not passed -> intact True? receipt_sha256 unchanged covers list
        # receipt_intact should already fail because the list is covered
        self.assertFalse(receipt_intact(r))


class TestScene(unittest.TestCase):
    def test_deterministic(self):
        a = gradient_scene(20, 20)
        b = gradient_scene(20, 20)
        self.assertEqual(a, b)

    def test_edit_changes_bytes(self):
        px = gradient_scene(20, 20)
        e = edit_region(px, 20, 20, 3, 5, 5, 5, 5)
        self.assertNotEqual(px, e)
        # outside region untouched
        self.assertEqual(px[: (5 * 20 + 4) * 3], e[: (5 * 20 + 4) * 3])


class TestSha(unittest.TestCase):
    def test_known_digest(self):
        self.assertEqual(sha256_hex(b"abc"), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")


if __name__ == "__main__":
    unittest.main(verbosity=2)
