#!/usr/bin/env python3
"""Print one hash of the working tree's state, for check.sh's "checks changed nothing" guard.

Covers tracked and non-ignored files: each path's contents, its type and mode,
a symlink's exact target, git's status, and the index (blob ids and modes).
A path that cannot be read or stat-ed, including a symlink whose referent is
missing or cannot be reached, raises, so the guard fails rather than leaving
that path out of both snapshots.
"""
import hashlib
import os
import stat
import subprocess


def tree_state(cwd="."):
    h = hashlib.sha256()
    # git ls-files exits 0 even when it cannot open a directory; its warning on
    # stderr is the only sign a path is missing, so any stderr fails the snapshot.
    listing = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                             cwd=cwd, capture_output=True, check=True)
    if listing.stderr:
        raise RuntimeError("git ls-files: " + listing.stderr.decode(errors="replace").strip())
    names = listing.stdout
    for name in sorted(n for n in names.split(b"\0") if n):
        path = os.path.join(cwd, os.fsdecode(name))
        st = os.lstat(path)                                  # the entry, not what it points to
        h.update(name + b"\0" + oct(st.st_mode).encode())    # type and permission bits
        if stat.S_ISLNK(st.st_mode):
            h.update(b"link:" + os.fsencode(os.readlink(path)))  # exact target bytes
            ref = os.stat(path)                              # follows the link; a missing or blocked referent raises
            if stat.S_ISREG(ref.st_mode):                    # and what it points to; a failed read raises
                with open(path, "rb") as f:
                    h.update(hashlib.sha256(f.read()).digest())
            else:                                            # a directory or device cannot be read as one file
                raise IsADirectoryError(f"{path}: symlink to a non-regular file; the guard cannot read it")
        elif stat.S_ISREG(st.st_mode):
            with open(path, "rb") as f:                      # opened directly: '-' is never stdin
                h.update(hashlib.sha256(f.read()).digest())
        else:                                                # e.g. an untracked nested repository, listed as a directory
            raise IsADirectoryError(f"{path}: listed by git but not a file or symlink; the guard cannot read it")
    h.update(subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=all"], cwd=cwd))
    h.update(subprocess.check_output(["git", "ls-files", "--stage", "-z"], cwd=cwd))
    return h.hexdigest()


if __name__ == "__main__":
    print(tree_state())
