"""Non-interactive, atomic review CLI."""
import os
import sys
import tempfile
from pathlib import Path
from .review import ReviewError, config_from, load_json, make_review
from .parser import PlanError
from .reports import render

def add_review_command(sub):
    parser = sub.add_parser('review', help='CI向けレビューと自己完結レポート')
    parser.add_argument('plan')
    parser.add_argument('--format', choices=['json', 'markdown', 'html'], default='markdown')
    parser.add_argument('--output')
    parser.add_argument('--config')
    parser.add_argument('--baseline')
    parser.add_argument('--target', default='default')
    parser.add_argument('--commit')
    parser.add_argument('--pr', type=int)
    parser.add_argument('--run-id', type=int)
    return parser

def write_output(path, text, limit):
    if len(text.encode('utf-8')) > limit:
        raise ReviewError('出力サイズ上限を超えました。出力は保存していません。')
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as stream:
            temporary = stream.name
            stream.write(text)
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)

def run_review(args):
    try:
        config = config_from(load_json(args.config, 1024*1024) if args.config else None)
        if args.output and any(Path(args.output).resolve() == Path(p).resolve() for p in (args.plan, args.config, args.baseline) if p):
            raise ReviewError('入力ファイルを出力先に指定できません。')
        baseline, notice = None, None
        if args.baseline:
            try:
                baseline = load_json(args.baseline, config['max_input_bytes'])
            except ReviewError:
                notice = True
        report = make_review(load_json(args.plan, config['max_input_bytes']), config, target=args.target,
                             commit=args.commit, pr=args.pr, run_id=args.run_id, baseline=baseline, baseline_notice=notice)
        text = render(report, args.format)
        if len(text.encode('utf-8')) > config['max_output_bytes']:
            raise ReviewError('出力サイズ上限を超えました。')
        if args.output:
            write_output(args.output, text, config['max_output_bytes'])
        else:
            sys.stdout.write(text)
        return report['check']['exit_code']
    except (ReviewError, PlanError) as error:
        print('エラー: ' + str(error), file=sys.stderr)
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        print('エラー: レビューを完了できません。入力・設定・出力先を確認してください。', file=sys.stderr)
    return 2
