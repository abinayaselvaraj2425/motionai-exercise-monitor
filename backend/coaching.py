"""Evidence-linked, plain-language coaching. No inferred diagnosis or ideal score."""
import numpy as np

GUIDES = {
    'squat': ('Lowering and standing back up', 'Keep your whole foot on the floor, bend at your hips and knees, and stand back up at a comfortable pace.', 'Practise a few comfortable bends with the camera at your side. Choose a depth you can repeat without forcing it.'),
    'lunge': ('Lowering in a split stance', 'Place one foot ahead of the other, lower between your feet, then rise with control. Keep the front foot planted.', 'Try a shorter split stance first. Keep the same stance while you practise lowering and rising, then change sides.'),
    'push_up': ('Lowering and pressing up', 'Move your chest and hips together as you bend and straighten your arms. Keep your hands on a stable surface.', 'If keeping one long body line is difficult, try an easier incline variation. Use the same variation for your next comparison.'),
    'shoulder_press': ('Pressing up and lowering', 'Begin with bent elbows. Send your hands upward beside your head, keeping your wrists roughly above your elbows, then lower with control.', 'Practise a few slow presses at a comfortable height. A recognised rep does not require your elbows to lock straight.'),
    'jumping_jack': ('Opening and closing together', 'Open your arms and feet together, then bring both back towards the start. Make space around you.', 'Try stepping one foot out at a time while your arms rise if jumping is difficult. Start small and aim for coordinated opening and closing.'),
}

def coaching(ex, frames, cycles, coverage, usable, metrics, primary, gestures, angle):
    """Recompute from visible image/world joints, never imported feedback fields.

    Technique proportions are tracked seconds (gaps over 650 ms excluded), not
    diagnostic probabilities. Only sustained evidence produces a technique card.
    """
    evidence={k:[0.,0.] for k in ('body_line','forearm','lean','sides','gesture')}
    def visible(image, ids):
        return all(image[j].get('visibility',0)>=.45 and -.025<=image[j]['x']<=1.025 and -.025<=image[j]['y']<=1.025 for j in ids)
    previous=-1
    for i,f in enumerate(frames):
        t=f['timestamp']/1000;elapsed=t-previous
        dt=elapsed if previous>=0 and 0<elapsed<=.65 else 0;previous=t
        if primary[i] is None or i==0 or primary[i-1] is None:continue
        image=f['image'];world=[[p['x'],p['y'],p['z']] for p in f['world']]
        # Prefer the side with the best minimum visibility, just as live tracking does.
        candidates=[o for o in (0,1) if visible(image,[11+o,23+o])]
        if not candidates:continue
        o=max(candidates,key=lambda o:min(image[j]['visibility'] for j in (11+o,23+o)))
        def add(key,bad):evidence[key][0]+=dt*bool(bad);evidence[key][1]+=dt
        if ex=='push_up' and visible(image,[11+o,23+o,27+o]):
            value=angle(world,(11+o,23+o,27+o))
            if value is not None:add('body_line',value<155)
        if ex=='shoulder_press' and visible(image,[13+o,15+o]):
            dx=abs(image[15+o]['x']-image[13+o]['x'])*f['width'];dy=abs(image[15+o]['y']-image[13+o]['y'])*f['height']
            if dx+dy>1:add('forearm',dx>dy*.7)
        if ex in ('squat','lunge'):
            dx=abs(image[11+o]['x']-image[23+o]['x'])*f['width'];dy=abs(image[11+o]['y']-image[23+o]['y'])*f['height']
            if dy>1:add('lean',dx>dy*.9)
        if ex!='lunge':
            ids={'squat':[(23,25,27),(24,26,28)],'push_up':[(11,13,15),(12,14,16)],'shoulder_press':[(11,13,15),(12,14,16)],'jumping_jack':[(23,11,13),(24,12,14)]}[ex]
            if all(visible(image,list(side)) for side in ids):
                a,b=[angle(world,side) for side in ids]
                if a is not None and b is not None:add('sides',abs(a-b)>25)
        # This check is only interpreted at the moving end, not while resting.
        moving=primary[i]>(65 if ex=='jumping_jack' else 135) if ex in ('jumping_jack','shoulder_press') else primary[i]<135
        if moving and ex in ('lunge','shoulder_press','jumping_jack'):add('gesture',not gestures[i])
    cards=[]
    def card(key,title,observed,action):
        bad,total=evidence[key]
        if total>=1 and bad>=.6 and bad/total>=.25:
            cards.append(dict(key=key,title=title,observed=observed,action=action,evidence=f'Seen in about {round(100*bad/total)}% of the time this feature could be checked.',kind='observed'))
    card('body_line','Keep your body moving as one piece','Your shoulders, hips and ankles did not always form one long line in the camera estimate.','Move your hips and chest together. Try a higher stable surface if that makes the movement easier to control.')
    card('forearm','Bring your wrists over your elbows','Your forearms often appeared to slant sideways in this camera view.','Bring your hands more directly above your elbows as you press. Check the camera is facing you before changing your technique.')
    card('lean','Keep your chest a little more lifted','Your upper body often leaned forward in the camera view. Some forward lean is normal and depends on the exercise and your proportions.','Try a smaller comfortable bend while keeping your chest lifted. Compare using the same camera position.')
    card('sides','Help both sides move together','The two visible sides often showed different amounts of bending. Camera angle can contribute to this.','Move slowly with both sides in view. Check your camera position before treating this as a technique difference.')
    actions={'lunge':'Keep one foot ahead of the other while lowering and rising. Show both feet from a side or three-quarter view.', 'shoulder_press':'Move your hands upward beside your head rather than only bending your elbows in front of you.', 'jumping_jack':'Try opening your feet and raising your arms together, then closing both together. A step-out version is okay.'}
    if ex in actions:card('gesture','Make the selected movement clearer','Some moving sections did not show all the features needed to recognise this exercise.',actions[ex])
    if len(cycles)>=3:
        ranges=np.asarray([c['range'] for c in cycles],dtype=float)
        typical_range=float(np.median(ranges));range_spread=float(np.median(np.abs(ranges-typical_range)))
        cards.append(dict(key='repeatability',title='Choose a bend you can repeat',kind='observed',observed='You used a fairly similar amount of bending from one complete movement to the next.' if range_spread<=typical_range*.15 else 'The amount of bending changed between your complete movements.',action='Aim for a comfortable movement you can repeat. If the next rep feels harder to control, make it smaller or take a break rather than forcing a deeper bend.',evidence=f'Compared the amount of bending across {len(cycles)} complete measurable movements.'))
        durations=[c['duration'] for c in cycles];typical=float(np.median(durations))
        spread=float(np.median(np.abs(np.array(durations)-typical)))
        cards.append(dict(key='rhythm',title='Find a repeatable rhythm',kind='observed',observed='Your completed movements took fairly similar amounts of time.' if spread<=typical*.2 else 'The time taken to complete each movement varied across the set.',action='Keep a pace you can repeat. Lower and return with control; there is no need to race the counter.',evidence=f'Based on {len(cycles)} complete measurable movements.'))
    if len(cycles)>=6:
        early=float(np.median([c['range'] for c in cycles[:3]]));late=float(np.median([c['range'] for c in cycles[-3:]]))
        if late<early*.8:
            cards.append(dict(key='set_change',title='Keep the last movements comfortable',kind='observed',observed='Your last three measurable movements used a smaller bend than your first three. The recording cannot tell us why.',action='Try fewer repetitions or a short rest so you can repeat a comfortable movement. Do not force a deeper bend to match an earlier rep.',evidence='Compared the first and last three measurable movements.'))
    if coverage<60 or not usable:
        cards.insert(0,dict(key='tracking',title='Give the camera a clearer view',kind='tracking',observed='Much of this session could not be measured clearly, so technique findings may be incomplete.',action='Keep the required joints inside the frame, use even lighting, and follow the suggested camera view. Try a short test before your next set.',evidence=f'Estimated tracking coverage: {coverage}%.'))
    if len(cycles)<2:
        cards.append(dict(key='short_set',title='Build a clearer movement sample',kind='tracking',observed='There were too few complete measurable movements to judge your rhythm or repeatability.',action='If comfortable, try a few complete movements from your starting position and back. You do not need to reach an exact angle.',evidence=f'{len(cycles)} complete measurable movements; saved live repetitions are kept separately.'))
    title,how,practice=GUIDES[ex]
    cards.append(dict(key='practice',title=title,kind='practice',observed='A practice suggestion for this exercise, rather than a detected fault.',action=how+' '+practice,evidence='Exercise guide.'))
    summary=(f'We could describe {len(cycles)} complete movements in this recording. '+('Use the observations below to choose one small adjustment for your next set.' if cards else 'Keep practising at a comfortable, repeatable pace.')) if usable else 'Your session was saved, but tracking was too limited for a detailed judgement about your technique.'
    return dict(summary=summary,cards=cards,next_session=[c['action'] for c in cards if c['kind']!='practice'][:2]+[practice],scope='Based on estimated visible joint positions. A counted repetition means a recognised movement cycle, not a certificate of correct technique.')
