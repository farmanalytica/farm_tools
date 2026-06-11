# -*- coding: utf-8 -*-
"""Compile Qt .ts (XML) translation files to .qm binary format."""

import os
import struct
import xml.etree.ElementTree as ET
from io import BytesIO

MAGIC = bytes([
    0x3c, 0xb8, 0x64, 0x18, 0xca, 0xef, 0x9c, 0x95,
    0xcd, 0x21, 0x1c, 0xbf, 0x60, 0xa1, 0xbd, 0xdd,
])

SEC_HASHES = 0x42
SEC_MESSAGES = 0x69
SEC_DEPENDENCIES = 0x84

TAG_END = 1
TAG_TRANSLATION = 3
TAG_SOURCE = 6
TAG_COMMENT = 7


def _elf_hash(data: bytes) -> int:
    h = 0
    for b in data:
        h = ((h << 4) + b) & 0xffffffff
        g = h & 0xf0000000
        if g:
            h ^= g >> 24
        h &= (~g) & 0xffffffff
    return h


def _msg_hash(source: str) -> int:
    return _elf_hash(source.encode('utf-8'))


def _encode_message(source: str, translation: str, context: str) -> bytes:
    buf = BytesIO()
    src = source.encode('utf-8') + b'\x00'
    buf.write(struct.pack('>BI', TAG_SOURCE, len(src)))
    buf.write(src)
    ctx = context.encode('utf-8') + b'\x00'
    buf.write(struct.pack('>BI', TAG_COMMENT, len(ctx)))
    buf.write(ctx)
    trans = translation.encode('utf-16-be')
    buf.write(struct.pack('>BI', TAG_TRANSLATION, len(trans)))
    buf.write(trans)
    buf.write(struct.pack('>B', TAG_END))
    return buf.getvalue()


def compile_ts(ts_path: str, qm_path: str) -> None:
    tree = ET.parse(ts_path)
    root = tree.getroot()

    entries = []
    for ctx_el in root.findall('context'):
        ctx = ctx_el.findtext('name', '')
        for msg_el in ctx_el.findall('message'):
            source = msg_el.findtext('source', '')
            trans_el = msg_el.find('translation')
            if trans_el is None:
                continue
            if trans_el.get('type', '') in ('obsolete', 'vanished', 'unfinished'):
                continue
            translation = trans_el.text or ''
            comment = msg_el.findtext('comment', '')
            entries.append((source, translation, comment, ctx))

    msg_buf = BytesIO()
    hash_pairs = []
    for source, translation, comment, ctx in entries:
        offset = msg_buf.tell()
        msg_buf.write(_encode_message(source, translation, ctx))
        hash_pairs.append((_msg_hash(source), offset))

    hash_pairs.sort()

    hash_buf = BytesIO()
    for h, offset in hash_pairs:
        hash_buf.write(struct.pack('>II', h, offset))

    with open(qm_path, 'wb') as f:
        f.write(MAGIC)
        for sec_type, data in (
            (SEC_HASHES, hash_buf.getvalue()),
            (SEC_MESSAGES, msg_buf.getvalue()),
            (SEC_DEPENDENCIES, b''),
        ):
            f.write(struct.pack('>BI', sec_type, len(data)))
            f.write(data)

    print(f'  {os.path.basename(ts_path)} -> {os.path.basename(qm_path)} ({len(entries)} messages)')


if __name__ == '__main__':
    i18n_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'i18n')
    ts_files = sorted(f for f in os.listdir(i18n_dir) if f.endswith('.ts'))
    print(f'Compiling {len(ts_files)} .ts files...')
    for ts_file in ts_files:
        compile_ts(
            os.path.join(i18n_dir, ts_file),
            os.path.join(i18n_dir, ts_file[:-3] + '.qm'),
        )
    print('Done.')
