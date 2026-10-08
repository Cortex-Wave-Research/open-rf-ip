#!/usr/bin/env python3
"""Maintenance-only VexRiscv regeneration/check; never writes the canonical files."""

import argparse
import hashlib
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = "https://github.com/SpinalHDL/VexRiscv.git"
REVISION = "baf7dc82f855eddaf5b0a20a6802c526f127e38a"
GENERATOR = "vexriscv.demo.GenSmallestNoCsr"
RTL_SHA256 = "0929e8fa42b8f6641fbb4c09b2ca65132ae7cf63777f16010151fa372852463c"
LICENSE_SHA256 = "230178ba3f6cb6cf94ec301a9208fa6870e62c1ed83f20543f059622c3619760"
LAUNCHER_SHA256 = "627ddd9b3524369edaf891577a0c59e8bf70e783f751c12f4be779663ad29844"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(candidate):
    canonical = ROOT / "third_party/vexriscv/VexRiscv.v"
    require(digest(canonical) == RTL_SHA256, "canonical RTL hash mismatch")
    require(digest(ROOT / "third_party/vexriscv/LICENSE") == LICENSE_SHA256,
            "canonical LICENSE hash mismatch")
    actual = digest(candidate)
    print(f"SHA256 {actual}  {candidate}")
    require(actual == RTL_SHA256, "candidate RTL hash mismatch")
    data = candidate.read_bytes()
    require(data == canonical.read_bytes(), "candidate differs from canonical RTL")
    require(len(data) == 134457 and data.count(b"\n") == 2520,
            "unexpected RTL size or line count")


def output(args, cwd=None):
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def verify_checkout(checkout):
    git = ["git", "-C", str(checkout)]
    require(output(git + ["remote", "get-url", "origin"]) == UPSTREAM,
            "origin must be the official HTTPS upstream")
    require(output(git + ["rev-parse", "HEAD"]) == REVISION,
            "checkout is not at the pinned revision")
    require(not output(git + ["status", "--porcelain", "--untracked-files=no"]),
            "checkout has tracked modifications")
    require(digest(checkout / "LICENSE") == LICENSE_SHA256, "upstream LICENSE mismatch")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check", type=Path, metavar="RTL",
                       help="offline byte/hash check only; no Java, Git or network")
    modes.add_argument("--regenerate", action="store_true",
                       help="explicit maintenance operation; may download dependencies")
    parser.add_argument("--checkout", type=Path,
                        help="optional clean official pinned checkout to clone locally")
    parser.add_argument("--java-home", type=Path,
                        help="JDK 17 directory; defaults to JAVA_HOME")
    parser.add_argument("--sbt-launch", type=Path,
                        help="official SBT 1.6.0 sbt-launch.jar (hash verified)")
    args = parser.parse_args()
    if args.check:
        require(not (args.checkout or args.java_home or args.sbt_launch),
                "generation options cannot be used with --check")
        check(args.check)
        print("PASS: candidate and canonical snapshot are byte-identical")
        return

    check(ROOT / "third_party/vexriscv/VexRiscv.v")
    java_home = args.java_home or os.environ.get("JAVA_HOME")
    require(java_home, "set JAVA_HOME or --java-home to a compatible JDK 17")
    java_home = Path(java_home).resolve()
    java = java_home / "bin/java"
    javac = java_home / "bin/javac"
    for executable in (java, javac):
        version = subprocess.run([str(executable), "-version"], check=True,
                                 capture_output=True, text=True)
        text = version.stdout + version.stderr
        print(text.strip())
        require(re.search(r'(?:version\s+"|javac\s+)17\.', text),
                "JDK 17 compatibility required (both java and javac)")
    require(args.sbt_launch, "--sbt-launch is required; use official SBT 1.6.0")
    launcher = args.sbt_launch.resolve()
    require(digest(launcher) == LAUNCHER_SHA256, "SBT 1.6.0 launcher hash mismatch")
    if args.checkout:
        verify_checkout(args.checkout.resolve())

    # Each run is fresh, isolated and retained for auditing in ignored build/.
    base = ROOT / "build/vexriscv-regeneration"
    base.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="run-", dir=base))
    checkout = work / "upstream"
    source = str(args.checkout.resolve()) if args.checkout else UPSTREAM
    subprocess.run(["git", "clone", "--no-hardlinks", "--no-checkout", source,
                    str(checkout)], check=True)
    if args.checkout:
        subprocess.run(["git", "-C", str(checkout), "remote", "set-url", "origin",
                        UPSTREAM], check=True)
    subprocess.run(["git", "-C", str(checkout), "checkout", "--detach", REVISION],
                   check=True)
    verify_checkout(checkout)
    env = os.environ.copy()
    env["JAVA_HOME"] = str(java_home)
    env["PATH"] = str(java_home / "bin") + os.pathsep + env.get("PATH", "")
    env["COURSIER_CACHE"] = str(work / "cache/coursier")
    env["XDG_CACHE_HOME"] = str(work / "cache/xdg")
    repositories = work / "repositories"
    repositories.write_text("[repositories]\nlocal\nmaven-central: https://repo.maven.apache.org/maven2/\n")
    command = [str(java), "-Xmx2G", f"-Duser.home={work / 'home'}",
               f"-Dsbt.global.base={work / 'sbt-global'}",
               f"-Dsbt.boot.directory={work / 'sbt-boot'}",
               f"-Dsbt.ivy.home={work / 'ivy'}",
               f"-Dsbt.repository.config={repositories}",
               "-Dsbt.override.build.repos=true", "-Dsbt.supershell=false",
               "-jar", str(launcher), f"runMain {GENERATOR}"]
    (work / "command.txt").write_text(shlex.join(command) + "\n")
    print(f"Working directory: {checkout}\nCommand: {shlex.join(command)}", flush=True)
    with (work / "generation.log").open("w") as log:
        subprocess.run(command, cwd=checkout, env=env, stdout=log,
                       stderr=subprocess.STDOUT, check=True)
    verify_checkout(checkout)
    check(checkout / "VexRiscv.v")
    print(f"PASS: regenerated RTL matches canonical snapshot; audit: {work}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        sys.exit(1)
