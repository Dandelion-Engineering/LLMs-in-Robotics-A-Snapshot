from attempts import *
transcript=REPO/'chats/Codex-Human/Apartment Fresh Pair Commissioning and Baseline Launch/Apartment Fresh Pair Commissioning and Baseline Launch - Active.md'
assert not (HERE/'authority-original.md').exists()
shutil.copyfile(transcript,HERE/'authority-original.md')
freeze_release()
register('preservation001','preserve.py','Inventory every older official and engineering history before integrated commissioning; authenticate the frozen prospective release and retained Session 38 official baseline.')
build()
