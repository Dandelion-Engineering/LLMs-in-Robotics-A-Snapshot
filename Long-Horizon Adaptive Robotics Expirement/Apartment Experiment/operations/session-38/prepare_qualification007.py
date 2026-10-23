from attempts import register
register('qualification007','qualify_workspace.py',
    'Final source qualification adds explicit fsync of adopted object/chunk directories before the first journal record. It preserves the original directory durability barrier and tests its failure without admitting a mount.',
    ['all qualification006 cases and unchanged deadlines','additional injected adopted-directory flush failure','passed qualification006 and audit001 remain distinct earlier results'],prior='APARTMENT-s38-qualification006')
