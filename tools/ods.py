"""Lecture d'une feuille d'un tableur OpenDocument (.ods) au format des données de Motion Twin (ods.Data) :
première ligne = noms de colonnes, une ligne commençant par « $ » termine la table."""
import zipfile
import xml.etree.ElementTree as ET

T = '{urn:oasis:names:tc:opendocument:xmlns:table:1.0}'
P = '{urn:oasis:names:tc:opendocument:xmlns:text:1.0}p'


def rows(path, sheet):
    root = ET.fromstring(zipfile.ZipFile(path).read('content.xml'))
    for table in root.iter(T + 'table'):
        if table.get(T + 'name') != sheet:
            continue
        rows = []
        for r in table.iter(T + 'table-row'):
            cells = []
            for c in r.findall(T + 'table-cell'):
                n = min(int(c.get(T + 'number-columns-repeated', '1')), 64)
                cells += ['\n'.join(''.join(p.itertext()) for p in c.findall(P))] * n
            while cells and cells[-1] == '':
                cells.pop()
            if cells:
                rows.append(cells)
        head = rows[0]
        out = []
        for r in rows[1:]:
            if r[0].startswith('$'):  # fin de table du format ods.Data de Motion Twin
                break
            out.append(dict(zip(head, r + [''] * (len(head) - len(r)))))
        return out
    raise KeyError(sheet)
