import os, tempfile, unittest
import pdfread


def make_pdf(path, w, h, text):
    body = "BT /F1 12 Tf 20 %d Td (%s) Tj ET" % (h - 40, text)
    objs = ["<</Type/Catalog/Pages 2 0 R>>", "<</Type/Pages/Kids[3 0 R]/Count 1>>",
            "<</Type/Page/Parent 2 0 R/MediaBox[0 0 %d %d]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>" % (w, h),
            "<</Length %d>>\nstream\n%s\nendstream" % (len(body), body), "<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>"]
    out, offs = "%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out)); out += "%d 0 obj\n%s\nendobj\n" % (i, o)
    x = len(out)
    out += "xref\n0 6\n0000000000 65535 f \n" + "".join("%010d 00000 n \n" % o for o in offs)
    out += "trailer<</Size 6/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF\n" % x
    open(path, "w").write(out)


class PdfRead(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.inbox = os.path.join(self.d, "inbox"); os.makedirs(self.inbox)

    def test_text_and_slices_of_a_tall_page(self):
        p = os.path.join(self.inbox, "a.pdf"); make_pdf(p, 600, 6000, "hello tall page")
        r = pdfread.pdf_read({"path": p}, inbox=self.inbox)
        self.assertIn("hello tall page", r["text"])
        r = pdfread.pdf_read({"path": p, "page": 1}, inbox=self.inbox)
        self.assertEqual(len(r["slices"]), pdfread.MAX_SLICES)
        self.assertIn("from_slice=%d" % (pdfread.MAX_SLICES + 1), r["next"])
        self.assertTrue(all(os.path.dirname(f) == self.inbox and os.path.getsize(f) for f in r["slices"]))
        r = pdfread.pdf_read({"path": p, "page": 1, "from_slice": r["slices_total"]}, inbox=self.inbox)
        self.assertEqual(len(r["slices"]), 1)

    def test_only_pdfs_in_the_inbox(self):
        p = os.path.join(self.d, "outside.pdf"); make_pdf(p, 600, 800, "x")
        with self.assertRaises(ValueError):
            pdfread.pdf_read({"path": p}, inbox=self.inbox)
        link = os.path.join(self.inbox, "l.pdf"); os.symlink(p, link)
        with self.assertRaises(ValueError):
            pdfread.pdf_read({"path": link}, inbox=self.inbox)
        with self.assertRaises(ValueError):
            pdfread.pdf_read({"path": "/etc/passwd"}, inbox=self.inbox)


if __name__ == "__main__":
    unittest.main()
