"""Local, syntax-only documentation and call-pattern audit."""
import argparse
import ast
import json
import os
from pathlib import Path
import re
import sys

from . import __version__
from .phrases import (STYLETRANSFER, NOSTYLETRANSFER, GENERIC_NAMES,
                      OPENCV_NAMES, MAGENTA_NAMES, MAGENTA_URL, FAST_IMPORTS)


def normalize(text):
    return ' '.join(text.lower().replace("n't", ' not').replace('-', ' ').split())


def prose(text):
    lines = []
    fence = None
    for line in text.splitlines():
        match = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line)
        if fence:
            if match and match[1][0] == fence[0] and len(match[1]) >= len(fence) and not match[2].strip():
                fence = None
            lines.append('')
        elif match:
            fence = match[1]
            lines.append('')
        else:
            lines.append(line)
    return re.split(r'\n\s*\n', '\n'.join(lines))


def pattern(phrases):
    return re.compile(r'\b(?:' + '|'.join(re.escape(p) for p in sorted(phrases, key=lambda p: (-len(p), p))) + r')\b')


POSITIVE = pattern(STYLETRANSFER)
NEGATIVE = pattern(NOSTYLETRANSFER)


def claims(text):
    yes = no = False
    for paragraph in prose(text):
        paragraph = normalize(paragraph)
        no = no or bool(NEGATIVE.search(paragraph))
        paragraph = NEGATIVE.sub(lambda m: ' ' * len(m[0]), paragraph)
        yes = yes or bool(POSITIVE.search(paragraph))
    return yes, no


def has_evidence(source):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    nodes = list(ast.walk(tree))
    shadows = {n.name for n in nodes if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    imports = {}
    modules = set()
    bindings = {}
    for n in nodes:
        if isinstance(n, ast.Import):
            for a in n.names:
                modules.add(a.name)
                imports[a.asname or a.name.split('.')[0]] = a.name if a.asname else a.name.split('.')[0]
        elif isinstance(n, ast.ImportFrom):
            mod = n.module or ''
            modules.add(mod)
            for a in n.names:
                imports[a.asname or a.name] = mod + '.' + a.name
        elif isinstance(n, (ast.Assign, ast.AnnAssign)):
            targets = n.targets if isinstance(n, ast.Assign) else [n.target]
            for target in targets:
                for child in ast.walk(target):
                    if isinstance(child, ast.Name):
                        bindings[child.id] = n.value
        elif isinstance(n, (ast.With, ast.AsyncWith)):
            for item in n.items:
                if item.optional_vars:
                    for child in ast.walk(item.optional_vars):
                        if isinstance(child, ast.Name):
                            bindings[child.id] = item.context_expr

    def resolved(n):
        if isinstance(n, ast.Name):
            if n.id in shadows or n.id in bindings:
                return ''
            return imports.get(n.id, '')
        if isinstance(n, ast.Attribute):
            base = resolved(n.value)
            return base + '.' + n.attr if base else ''
        return ''

    def name(n):
        return n.id if isinstance(n, ast.Name) else n.attr if isinstance(n, ast.Attribute) else ''

    def shadowed(n):
        if name(n) in shadows:
            return True
        while isinstance(n, ast.Attribute):
            n = n.value
        return isinstance(n, ast.Name) and (n.id in shadows or (n.id in imports and n.id in bindings))

    cv_gate = any(m == 'cv2' or m.startswith('cv2.') for m in modules)
    hub_gate = any(m == 'tensorflow_hub' or m.startswith('tensorflow_hub.') for m in modules)
    fast_gate = any(any(x in m for x in FAST_IMPORTS) for m in modules)

    def construction(n):
        if not isinstance(n, ast.Call) or shadowed(n.func):
            return False
        f = n.func
        route = resolved(f)
        hub_func = (isinstance(f, ast.Attribute) and name(f.value) == 'hub' and f.attr in MAGENTA_NAMES) or (route.startswith('tensorflow_hub.') and route.split('.')[-1] in MAGENTA_NAMES)
        if hub_gate and hub_func:
            args = list(n.args[:1]) + [k.value for k in n.keywords if k.arg in ('url', 'handle')]
            return any(isinstance(a, ast.Constant) and isinstance(a.value, str) and MAGENTA_URL in a.value for a in args)
        return fast_gate and (name(f) == 'TransformerNet' or route.split('.')[-1] == 'TransformerNet')

    def model(n):
        if isinstance(n, ast.Name):
            return n.id not in shadows and construction(bindings.get(n.id))
        return construction(n)

    for n in nodes:
        if not isinstance(n, ast.Call) or shadowed(n.func):
            continue
        f = n.func
        route = resolved(f)
        if isinstance(f, ast.Attribute) and f.attr in GENERIC_NAMES:
            return True
        if isinstance(f, ast.Name) and route and route.split('.')[-1] in GENERIC_NAMES:
            return True
        if cv_gate:
            if isinstance(f, ast.Attribute) and (f.attr in OPENCV_NAMES or (f.attr == 'oilPainting' and isinstance(f.value, ast.Attribute) and f.value.attr == 'xphoto')):
                return True
            if route.startswith('cv2.') and (route.split('.')[-1] in OPENCV_NAMES or route.endswith('.xphoto.oilPainting')):
                return True
        if model(f) or (isinstance(f, ast.Attribute) and model(f.value)):
            return True
    return False


def audit(repo='.', ignore=()):
    root = Path(repo)
    if not root.is_dir():
        raise OSError('Repository is not a directory: ' + str(root))
    positive = negative = False
    production, tests = [], []
    def excluded(rel):
        return any(rel == p.rstrip('/') or rel.startswith(p.rstrip('/') + '/') for p in ignore)
    for directory, dirs, files in os.walk(root, onerror=lambda e: (_ for _ in ()).throw(e), followlinks=False):
        base = Path(directory)
        dirs[:] = sorted(d for d in dirs if not (base / d).is_symlink() and not excluded((base / d).relative_to(root).as_posix()))
        for filename in sorted(files):
            path = base / filename
            rel = path.relative_to(root)
            if path.is_symlink() or excluded(rel.as_posix()):
                continue
            if rel.as_posix() == 'README.md' or (path.suffix == '.md' and 'docs' in rel.parts):
                yes, no = claims(path.read_text(encoding='utf-8'))
                positive |= yes
                negative |= no
            if path.suffix != '.py' or set(rel.parts[:-1]) & {'fixtures', 'docs', 'examples'}:
                continue
            if has_evidence(path.read_text(encoding='utf-8')):
                is_test = 'tests' in rel.parts[:-1] or filename.startswith('test_') or filename.endswith('_test.py')
                (tests if is_test else production).append(rel.as_posix())
    findings = []
    if positive and not production:
        severity = 'MEDIUM' if tests else 'HIGH'
        findings.append({'id': 'documented-image-style-transfer-claim-false', 'severity': severity,
                         'message': 'The documented capability has evidence only in tests.' if tests else 'The documented capability has no production evidence.'})
    if negative and production:
        findings.append({'id': 'documented-no-image-style-transfer-claim-false', 'severity': 'HIGH',
                         'message': 'Documentation denies a capability present in production source.'})
    return {'verdict': 'FAIL' if findings else 'PASS', 'findings': findings,
            'evidence': {'production': production, 'tests': tests}}


class Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(1, self.prog + ': error: ' + message + '\n')


def main(argv=None):
    parser = Parser(prog='image-style-transfer-claim-audit')
    parser.add_argument('--version', action='version', version=__version__)
    sub = parser.add_subparsers(dest='command', required=True, parser_class=Parser)
    cmd = sub.add_parser('audit')
    cmd.add_argument('repo', nargs='?', default='.')
    cmd.add_argument('--fail-on', choices=('high', 'medium'), default='high')
    cmd.add_argument('--ignore', action='append', default=[], metavar='PREFIX')
    cmd.add_argument('--json', action='store_true')
    cmd.add_argument('--verbose', action='store_true')
    args = parser.parse_args(argv)
    try:
        result = audit(args.repo, args.ignore)
    except (OSError, UnicodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(result['verdict'])
        for finding in result['findings']:
            print('{id} {severity}: {message}'.format(**finding))
        if args.verbose:
            print(json.dumps(result['evidence'], sort_keys=True))
    return 2 if any(f['severity'] == 'HIGH' or args.fail_on == 'medium' for f in result['findings']) else 0
