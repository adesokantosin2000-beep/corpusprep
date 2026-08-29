#!/usr/bin/env python3
"""
make_multilingual_fixtures.py — texts that are not English.

    python tools/make_multilingual_fixtures.py

Writes three fixtures and their region keys:

    tests/fixtures/de_kapitel.txt      German, Latin-1 range, ß and umlauts
    tests/fixtures/ru_glava.txt        Russian, Cyrillic throughout
    tests/fixtures/cs_kapitola.txt     Czech, dense diacritics including ř ů ě

**Every measured number in this repository is English literary prose.** That is
the largest unexamined assumption in the package: each rule was written by
someone reading English, tested on English, and its thresholds tuned on
English. A rule can be right about English and wrong about a language whose
sentences are longer, whose capitalisation rules differ — German capitalises
every noun — or whose alphabet is not Latin at all.

**These fixtures are original prose written for this purpose, not quotations.**
That keeps them free of licence questions and, more importantly, keeps their
structure exact: the generator records the region boundaries as it writes them,
so the key owes nothing to the tool it tests.

What they can show: that import, encoding detection, tokenising, casing,
hyphen repair, wrapping and the protected-span signals behave on non-ASCII
text, and that division headings are found in the words those languages use.

What they cannot show: anything about real literary corpora in these
languages. Synthetic prose has the regularity of its generator. A German novel
from a real scan remains the test that matters, and it is not in this
repository.

Deterministic: no randomness at all.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# --- German ---------------------------------------------------------------
DE = {
    "stem": "de_kapitel",
    "title": "Die Straße nach Süden",
    "author": "Für dieses Projekt geschrieben",
    "division": "Kapitel",
    "chapters": [
        ("Kapitel I", [
            "Der Morgen kam grau über die Dächer der kleinen Stadt, und die "
            "Bäckerin öffnete ihre Läden früher als gewöhnlich, weil sie die "
            "Straße noch leer sehen wollte. Es roch nach nassem Stein und "
            "nach dem Rauch, den der Wind aus den Kaminen herunterdrückte.",
            "Später sagte sie, sie habe nichts Besonderes bemerkt. Das war "
            "die Wahrheit und zugleich unvollständig, denn sie hatte den "
            "Fremden sehr wohl gesehen, wie er an der Mauer stand und die "
            "Aufschrift las, die dort seit dreißig Jahren verblaßte.",
        ]),
        ("Kapitel II", [
            "Im Amtszimmer war es wärmer. Der Schreiber legte die Feder "
            "beiseite, betrachtete seine Hände und stellte fest, daß sie "
            "zitterten. Draußen schlug die Turmuhr, und ihr Schlag klang "
            "über den Platz, als käme er aus großer Entfernung.",
            "»Sie müssen das unterschreiben«, sagte der Fremde. Der "
            "Schreiber antwortete nicht. Die Straße vor dem Fenster füllte "
            "sich langsam mit Menschen, die zum Markt gingen und nichts von "
            "dem wußten, was in diesem Zimmer verhandelt wurde.",
        ]),
    ],
}

# --- Russian --------------------------------------------------------------
RU = {
    "stem": "ru_glava",
    "title": "Дорога на юг",
    "author": "Написано для этого проекта",
    "division": "Глава",
    "chapters": [
        ("Глава I", [
            "Утро пришло серое, и над крышами маленького города долго стоял "
            "дым. Пекарка открыла ставни раньше обычного, потому что хотела "
            "увидеть улицу пустой. Пахло мокрым камнем и той горечью, "
            "которую ветер сносил с печных труб вниз, к самой земле.",
            "Позже она говорила, что не заметила ничего особенного. Это была "
            "правда и одновременно неполная правда, потому что незнакомца "
            "она видела очень хорошо: он стоял у стены и читал надпись, "
            "которая выцветала там уже тридцать лет.",
        ]),
        ("Глава II", [
            "В присутственной комнате было теплее. Писарь отложил перо, "
            "посмотрел на свои руки и понял, что они дрожат. За окном били "
            "башенные часы, и звук их шёл над площадью так, будто доносился "
            "издалека.",
            "«Вы должны это подписать», — сказал незнакомец. Писарь не "
            "ответил. Улица под окном медленно наполнялась людьми, которые "
            "шли на рынок и ничего не знали о том, что решалось в этой "
            "комнате.",
        ]),
    ],
}

# --- Czech ----------------------------------------------------------------
CS = {
    "stem": "cs_kapitola",
    "title": "Cesta na jih",
    "author": "Napsáno pro tento projekt",
    "division": "Kapitola",
    "chapters": [
        ("Kapitola I", [
            "Ráno přišlo šedivé a nad střechami městečka dlouho stál kouř. "
            "Pekařka otevřela okenice dříve než obvykle, protože chtěla "
            "vidět ulici prázdnou. Bylo cítit mokrý kámen a hořkost, kterou "
            "vítr srážel z komínů dolů k zemi.",
            "Později říkala, že si ničeho zvláštního nevšimla. Byla to pravda "
            "a zároveň pravda neúplná, neboť cizince viděla velmi dobře: stál "
            "u zdi a četl nápis, který tam už třicet let bledl.",
        ]),
        ("Kapitola II", [
            "V úřední místnosti bylo tepleji. Písař odložil pero, podíval se "
            "na své ruce a zjistil, že se mu třesou. Venku odbíjely věžní "
            "hodiny a jejich úder zněl přes náměstí, jako by přicházel z "
            "velké dálky.",
            "„Musíte to podepsat,“ řekl cizinec. Písař neodpověděl. Ulice pod "
            "oknem se pomalu plnila lidmi, kteří šli na trh a nevěděli nic o "
            "tom, co se v té místnosti projednávalo.",
        ]),
    ],
}

PG_HEAD = ("The Project Gutenberg eBook of {title}\n"
           "\n"
           "This ebook is for the use of anyone anywhere in the United States "
           "and\n"
           "most other parts of the world at no cost and with almost no "
           "restrictions\n"
           "whatsoever.\n"
           "\n"
           "Title: {title}\n"
           "Author: {author}\n"
           "\n"
           "*** START OF THE PROJECT GUTENBERG EBOOK {upper} ***\n")

PG_FOOT = ("*** END OF THE PROJECT GUTENBERG EBOOK {upper} ***\n"
           "\n"
           "Updated editions will be renamed.\n")


def build(spec: dict) -> None:
    lines: list[str] = []
    key: list[str] = []

    head = PG_HEAD.format(title=spec["title"], author=spec["author"],
                          upper=spec["title"].upper()).split("\n")
    lines += head
    key.append(f"1-{len(lines) - 1}\tpg_header")

    body_start = len(lines) + 1
    for name, paragraphs in spec["chapters"]:
        lines += ["", name, ""]
        for para in paragraphs:
            lines += textwrap.wrap(para, 64)
            lines.append("")
    while lines and not lines[-1].strip():
        lines.pop()
    key.append(f"{body_start}-{len(lines)}\tbody")

    foot_start = len(lines) + 2
    lines += ["", ""] + PG_FOOT.format(upper=spec["title"].upper()).split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    key.append(f"{foot_start}-{len(lines)}\tpg_licence")

    out = ROOT / "tests" / "fixtures" / f"{spec['stem']}.txt"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    kf = ROOT / "tests" / "keys" / f"{spec['stem']}.key"
    kf.write_text(
        f"# {spec['stem']}.txt — regions, recorded as the generator wrote them.\n"
        f"#\n"
        f"# Original prose written for this project, not a quotation. The\n"
        f"# division word is `{spec['division']}`, which is what the English\n"
        f"# heading tier has to know about for this file to segment at all.\n\n"
        + "\n".join(key) + "\n", encoding="utf-8")
    print(f"wrote {out.name}: {len(lines)} lines, {kf.name}: {len(key)} ranges")


for spec in (DE, RU, CS):
    build(spec)
