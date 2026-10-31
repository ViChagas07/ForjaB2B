import sys
import os

# Change to backend directory for alembic config
os.chdir('backend')

# Now import alembic (the installed package, not local directory)
from alembic.config import Config
from alembic.script import ScriptDirectory

alembic_cfg = Config('alembic.ini')
script = ScriptDirectory.from_config(alembic_cfg)

for revision in script.walk_revisions():
    if revision is None:
        continue
    if hasattr(revision, 'upgrade_ops') and revision.upgrade_ops:
        print(f'Revision {revision.revision}:')
        for op in revision.upgrade_ops.ops:
            print(f'  Op: {type(op).__name__}, table: {getattr(op, "table_name", None)}')
    else:
        print(f'Revision {revision.revision}: No upgrade_ops')