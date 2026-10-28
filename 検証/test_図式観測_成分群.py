"""公開盤面の連結成分が順序・被覆・最大性を保つことを検証する。"""

import random

from 接続.図式観測 import 成分群


def test_空盤面と不揃い盤面の成分順序():
    assert 成分群([]) == []
    assert 成分群([[], []]) == []
    board = [[1, 2, 1], [1], [2, 2]]
    actual = 成分群(board)
    assert [entry["点群"] for entry in actual] == [
        frozenset({(0, 0), (0, 1)}),
        frozenset({(0, 2), (1, 2)}),
        frozenset({(1, 0)}),
        frozenset({(2, 0)}),
    ]
    assert [entry["位置"] for entry in actual] == [(0, 0), (0, 2), (1, 0), (2, 0)]


def test_乱数盤面で各セルが同色4連結の最大成分に一度だけ含まれる():
    rng = random.Random(20261029)
    for _ in range(100):
        board = [[rng.randrange(4) for _ in range(rng.randrange(9))] for _ in range(rng.randrange(9))]
        components = 成分群(board)
        all_cells = {(x, y) for y, row in enumerate(board) for x in range(len(row))}
        owner = {}
        for index, entry in enumerate(components):
            cells = entry["点群"]
            assert cells and not (cells & owner.keys())
            owner.update({cell: index for cell in cells})
            color = board[next(iter(cells))[1]][next(iter(cells))[0]]
            assert all(board[y][x] == color for x, y in cells)
            left = min(x for x, _ in cells)
            top = min(y for _, y in cells)
            assert entry["位置"] == (left, top)
            assert entry["対応鍵"] == (color, tuple(sorted((x - left, y - top) for x, y in cells)))
            reached = {next(iter(cells))}
            pending = list(reached)
            while pending:
                x, y = pending.pop()
                for neighbor in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if neighbor in cells and neighbor not in reached:
                        reached.add(neighbor)
                        pending.append(neighbor)
            assert reached == cells
        assert set(owner) == all_cells
        assert [min(entry["点群"]) for entry in components] == sorted(min(entry["点群"]) for entry in components)
        for x, y in all_cells:
            for neighbor in ((x + 1, y), (x, y + 1)):
                if neighbor in all_cells and board[y][x] == board[neighbor[1]][neighbor[0]]:
                    assert owner[(x, y)] == owner[neighbor]
