"""
Comedy & Curiosity Story Generator (Hinglish + English Dual-Language Engine).
Replaces web news/trending scraping with genuinely funny, sarcastic, high-retention
8-beat stories modeled directly after the 5 Reference Reels:
  1. `tall_tale_3d`  (Ref 2: Weird laws, crazy loopholes, office/money roasts)
  2. `stick_story`   (Ref 4: Everyday science comedy, "Why does...", doodle world)
  3. `inside_out`    (Ref 5: Country vs Country & vehicle/design comparisons)
  4. `deep_dive_3d`  (Ref 1: Mechanical & body how-it-works with telemetry HUD)
  5. `night_file_3d` (Ref 3: Epic Indian mythology & wild historical twists)

Tracks used story IDs in `data/used_topics.json` so stories never repeat until all
have been seen.
"""
import hashlib
import json
import random
import urllib.parse
import urllib.request
from pathlib import Path

import props_engine
import scene_planner


def translate_text(text: str, target_lang: str) -> str:
    """Free zero-key translation for extra languages (es, fr, ja, pt, de)."""
    if target_lang in ("en", "hi"):
        return text
    try:
        q = urllib.parse.quote(text)
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl={target_lang}&dt=t&q={q}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
            out = "".join(seg[0] for seg in data[0] if seg and seg[0]).strip()
            if out:
                return out
    except Exception:
        pass
    return text

EXPRESSIONS = ["shocked", "smirk", "angry", "laughing", "shocked", "smirk", "angry", "laughing"]
POSES = ["hands_on_head", "pointing", "waving", "pointing", "hands_on_head", "waving", "pointing", "hands_on_head"]
CAMERAS = ["snap_zoom_in", "pan_left", "pan_right", "snap_zoom_in", "shake", "pan_left", "pan_right", "snap_zoom_in"]
SFX_SEQ = ["vine_boom", "pop", "whoosh", "ding", "pop", "vine_boom", "whoosh", "record_scratch"]


def classify_reference_style(text: str) -> str:
    low = text.lower()
    if any(k in low for k in ("ravan", "ram", "urmila", "laxman", "krishna", "mahabharat", "ramayan", "myth", "ancient", "king", "empire", "temple", "war", "warrior", "battle", "mystery", "ghost", "curse", "legend")):
        return "night_file_3d"
    if any(k in low for k in ("truck", "plane", "airplane", "aircraft", "train", "ship", "submarine", "versus", " vs ", "american", "british", "highway", "passport")):
        return "inside_out"
    if any(k in low for k in ("piston", "brake", "caliper", "engine", "motor", "nuclear", "battery", "hydraulic", "gear", "heart", "stomach", "brain", "dna", "acid", "gum")):
        return "deep_dive_3d"
    if any(k in low for k in ("power line", "wire", "cable", "heat", "cold", "summer", "winter", "sun", "moon", "sound", "noise", "pitch", "thermometer", "crack", "mirror", "pump")):
        return "stick_story"
    return "tall_tale_3d"


# Each entry: (title, category_label, style, [(hinglish_spoken, english_subtitle), ... 8 beats])
COMEDY_STORIES = [
    (
        "10 Questions Before Marriage: The Pizza & Last Fry Test! #Shorts",
        "2D Sitcom Skit (Rohan, Meera & Biscuit)",
        "tall_tale_3d",
        [
            ("Rohan: मीरा... तीन महीने में हमारी शादी है ना? मैंने दस खतरनाक सवाल तैयार किए हैं जो हमारा भविष्य तय करेंगे!", "Rohan: Meera, we're getting married in three months—so I prepared Ten Sacred Questions!"),
            ("Meera: शादी के कार्ड पे तो यही लिखा है। पर तुम ऐसे किडनैप हुए इंसान की तरह पसीना क्यों बहा रहे हो?!", "Meera: That's what the cards say. Why are you sweating like a hostage?!"),
            ("Rohan: सवाल नंबर एक—क्या तुम पिज़्ज़ा के ऊपर अनानास डालती हो? सोच के बोलना, हमारे बच्चों का सवाल है!", "Rohan: Question one: Do you put pineapple on pizza? Our children's future depends on this!"),
            ("Meera: हर बार! वो भी एक्स्ट्रा पाइनएप्पल के साथ। मीठा और नमकीन इसी को बैलेंस कहते हैं!", "Meera: Every single time—extra pineapple! Sweet and salty is called balance, bro."),
            ("Rohan: हे भगवान, मेरे साथ धोखा हुआ है! किसी ने बताया ही नहीं कि मेरी होने वाली बीवी क्रिमिनल है!", "Rohan: I feel betrayed! Nobody warned me my future wife was a literal criminal!"),
            ("Meera: अच्छा सुनो, अगर प्लेट में आखिरी फ्रेंच फ्राई बची हो, तो मैं प्यार से तुम्हें दे दूंगी...", "Meera: Fine—if one golden fry is left on the plate, I'll let you eat it out of love..."),
            ("Meera: ...बस शर्त ये है कि अगले पचास साल तक तुम्हें मेरा ये एहसान याद रखना पड़ेगा!", "Meera: ...the catch is you'll hear about my sacrifice for the next fifty years!"),
            ("Rohan: अरे देखो, बिस्किट बिल्ली हमारी आखिरी फ्राई चुरा के भाग गई—और यही वजह है कि...", "Rohan: Wait—our cat Biscuit just stole the last fry right off the table, which is why..."),
        ],
    ),
    (
        "Decoding 'I'm Fine' & The 16-Degree AC War! (Couple Skit) #Shorts",
        "2D Sitcom Skit (Rohan, Meera & Biscuit)",
        "tall_tale_3d",
        [
            ("Rohan: सवाल नंबर दो—शादी के बाद हमारे कमरे का एसी कितने डिग्री पर चलेगा? सोच समझकर बोलना!", "Rohan: Next question: What temperature will our bedroom AC be set to?!"),
            ("Meera: सोलह डिग्री! मुझे कमरा बिल्कुल फ्रिज जैसा ठंडा पसंद है, तुम अपना स्वेटर पहन लेना!", "Meera: Sixteen degrees! I like my room like a refrigerator—you can wear a sweater."),
            ("Rohan: सोलह डिग्री?! भाई मैं आइसक्रीम बन जाऊंगा और पेंगुइन हमारे बेडरूम में रहने आ जाएंगे!", "Rohan: Sixteen?! I'll freeze into a popsicle and penguins will move into our room!"),
            ("Rohan: अच्छा ये बताओ—जब तुम बोलती हो 'I am fine', तो उसका असली मतलब क्या होता है?!", "Rohan: Okay, next question: When you say 'I'm fine'... what does it actually mean?!"),
            ("Meera: उसका मतलब होता है कि मैं बिल्कुल ठीक हूँ। पर मेरी आइब्रो मत देखो, कमरे का तापमान देखो!", "Meera: It means I'm fine. Stop staring at my twitching eyebrow and check the room temperature!"),
            ("Rohan: भाई डायरी में लिख लेता हूँ—'I am fine' का मतलब सीधा खतरे की घंटी है!", "Rohan: Writing this down for survival: 'I'm fine' literally means immediate danger!"),
            ("Meera: चलो पास हो गए! अब मेरी बारी—ये बताओ जब से हम मिले हैं तुमने कितने मोज़े खोए हैं?!", "Meera: Question passed! Now my scroll: How many socks have you lost since we met?!"),
            ("Rohan: खोए नहीं हैं यार, कुछ मोज़े बस गुप्त यात्रा पर गए हैं, और यही वजह है कि...", "Rohan: They aren't lost, they're on a secret adventure—which is the exact reason why..."),
        ],
    ),
    (
        "Japan's Illegal Belly Law Measures Your Waist at Work?! #Shorts",
        "Weird Law Roast",
        "tall_tale_3d",
        [
            ("अरे bro, अगर तुम Japan में मोटे हुए ना, तो government सीधा तुम्हारी company पे fine ठोक देगी!", "In Japan, if your belly gets too big, the government literally fines your boss!"),
            ("मज़ाक नहीं यार, इसे Metabo Law कहते हैं और हर साल office में सबकी कमर नापी जाती है।", "Deadass, it's called the Metabo Law—every year, nurses pull out a tape at your office."),
            ("अगर तुम्हारी उम्र चालीस से ऊपर है और पेट पैंतीस इंच से बाहर निकला, तो समझो गए काम से!", "If you're over forty and your waist passes 33.5 inches, alarm bells go off!"),
            ("कंपनी के आधे अंकल लोग तो नाप के टाइम सांस अंदर खींच के खड़े हो जाते हैं!", "Half the office uncles literally suck their stomachs in praying the tape doesn't snap."),
            ("अगर तीन महीने में तोंद कम नहीं हुई, तो HR वाले तुम्हें जबरदस्ती diet class में भेजते हैं।", "Fail the check, and HR forces you into mandatory diet camp and gym sessions!"),
            ("और अगर कंपनी के लोग फिर भी पतले नहीं हुए, तो सरकार सीधा कंपनी पे करोड़ों का जुर्माना लगाती है!", "And if employees still stay chubby, the company gets slapped with massive cash penalties!"),
            ("इसी डर से वहां के boss खुद समोसे छीन के कर्मचारियों को सलाद खिलाते हैं...", "So Japanese bosses literally patrol the breakroom swapping donuts for green tea..."),
            ("...ताकि कंपनी कंगाल न हो जाए, और भाई यही पागलपन वजह है कि कैसे...", "...just to dodge the fat tax, which is the exact reason why..."),
        ],
    ),
    (
        "Why Tight Power Lines Scream at Night & Snap in Winter?! #Shorts",
        "Everyday Science Comedy",
        "stick_story",
        [
            ("भाई, कभी सोचा है कि बिजली के तार हमेशा ऐसे ढीले और लटके हुए क्यों लगाए जाते हैं?", "Ever wondered why power lines always hang loose instead of being pulled tight?!"),
            ("मान लो किसी आलसी engineer ने तार को बिल्कुल गिटार की तरह टाइट खींच के बांध दिया।", "Imagine an engineer pulls those metal cables tight as a guitar string between poles."),
            ("गर्मी में तो धूप पड़ते ही धातु फैलती है और तार और नीचे लटक जाता है।", "When summer heat hits, metal expands and the wire sags toward the houses anyway."),
            ("लेकिन असली कांड तब होता है जब रात को कड़ाके की ठंड पड़ती है!", "But the real disaster starts when freezing winter night rolls in, bro!"),
            ("ठंड से तार सिकुड़कर इतना टाइट हो जाता है कि हवा चलते ही अजीब सीटी बजाने लगता है!", "Cold shrinks the cable razor-tight until the wind makes it whine: EEEEEEE!"),
            ("मोहल्ले के लोग खिड़की बंद करके कान पकड़ लेते हैं पर वो तेज़ आवाज़ बंद ही नहीं होती।", "The whole neighborhood covers their ears at 3 AM while the pitch meter goes crazy!"),
            ("और थोड़ी और बर्फ गिरी तो तार सीधा बंदूक की गोली की तरह बीच से टूट जाता है...", "Drop the temperature ten more degrees and the tight wire snaps like a rubber band..."),
            ("...जिससे पूरे शहर की बत्ती गुल हो जाती है, और literally यही reason है कि...", "...blacking out the whole town, which is literally why..."),
        ],
    ),
    (
        "How ONE Brake Piston Squeezes Both Sides Without Bending the Wheel?! #Shorts",
        "Engineering Trick",
        "deep_dive_3d",
        [
            ("भाई, कार के ब्रेक में पिस्टन सिर्फ एक तरफ होता है—तो फिर वो पहिए को मोड़ के तोड़ क्यों नहीं देता?!", "Your car brake only has a piston on ONE side—so why doesn't it bend the wheel in half?!"),
            ("सोचो यार, अगर एक तरफ से हथौड़ा मारोगे तो डिस्क तो टेढ़ी हो जानी चाहिए ना?", "Think about it: pushing a spinning metal disc from one side should warp it instantly."),
            ("लेकिन engineers ने यहां दिमाग का सबसे शातिर जुगाड़ लगाया जिसे Floating Caliper कहते हैं!", "Instead, engineers used a genius mechanical cheat code called the Floating Caliper trick!"),
            ("जैसे ही तुम ब्रेक दबाते हो, अंदर का तेल पिस्टन को आगे धकेलता है।", "The second you stomp the pedal, fluid pressure blasts the inner pad against the rotor."),
            ("अंदर वाला पैड डिस्क से टकराकर वहीं रुक जाता है, पर प्रेशर रुकता नहीं है!", "Once that inner pad hits the spinning metal, it stops dead—but pressure keeps rising!"),
            ("तो न्यूटन के नियम से पूरा लोहे का ढांचा ही पीछे की तरफ फिसलने लगता है!", "So Newton's third law forces the ENTIRE metal housing to slide backward on pins!"),
            ("और पीछे खिसकते ही वो बाहर वाली उंगलियों से दूसरे पैड को भी कसके दबा देता है...", "That sliding frame yanks the outer brake pad inward like a giant metal claw..."),
            ("...जिससे एक ही पिस्टन दोनों तरफ बराबर ताकत लगाता है, और यही वजह है कि...", "...clamping both sides with one piston, which is the exact reason why..."),
        ],
    ),
    (
        "The Real Ego Mistake That Cost Ravan His Golden Lanka! #Shorts",
        "Mythology Twist",
        "night_file_3d",
        [
            ("रावण के पास सोने की लंका, मायावी शक्तियां और वरदान थे—फिर भी वो एक गलती से कैसे हार गया?!", "Ravan had a golden kingdom, cosmic weapons, and boons—so what single mistake destroyed him?!"),
            ("जब रावण ने ब्रह्मा जी से अमर होने का वरदान मांगा, तो उसने देवताओं और राक्षसों का नाम लिया।", "When Ravan demanded immortality from Brahma, he listed gods, demons, and serpents."),
            ("पर अपने घमंड में उसने इंसानों और वानरों को कीड़े-मकोड़े समझकर लिस्ट से छोड़ दिया!", "Out of pure arrogance, he laughed off humans and monkeys as too weak to mention!"),
            ("उसे लगा कोई साधारण इंसान समंदर पार करके उसकी लंका तक कभी पहुंच ही नहीं पाएगा।", "He swore no mortal could ever cross the ocean to touch his throne."),
            ("यहां तक कि जब उसके अपने भाई विभीषण ने उसे सच समझाया, तो रावण ने उसे लात मारकर निकाल दिया!", "When his own brother Vibhishan warned him, Ravan kicked him straight out of the court!"),
            ("और युद्ध की रात जब उसने मायावी तीर चलाए, तब विभीषण ने ही राम को उसकी नाभि का राज़ बता दिया!", "On the final battlefield, Vibhishan revealed the secret nectar hidden in Ravan's navel!"),
            ("जिस इंसान को उसने सबसे कमज़ोर समझा था, उसी के एक बाण ने उसका घमंड चूर कर दिया...", "The exact mortal he refused to fear fired the arrow that ended his reign..."),
            ("...और पूरी सोने की लंका देखते-देखते राख हो गई, और यही कारण है कि...", "...turning his unstoppable empire into ash, which is the exact reason why..."),
        ],
    ),
    (
        "Why American Trucks Have Huge Noses vs Flat British Trucks?! #Shorts",
        "Design Roast",
        "inside_out",
        [
            ("भाई, ब्रिटेन और इंडिया के ट्रक आगे से बिल्कुल चपटे होते हैं, पर अमेरिकी ट्रक की इतनी लंबी नाक क्यों होती है?!", "Ever noticed British trucks are totally flat, while American trucks have massive noses?!"),
            ("यह कोई स्टाइल मारने के लिए नहीं है यार, इसके पीछे सरकार का एक अजीब कानून छुपा है।", "It's not for style, bro—it comes down to one weird government measurement law."),
            ("यूरोप और ब्रिटेन में सरकार पूरे ट्रक की लंबाई नापती है, बंपर से लेकर पीछे के कोने तक!", "In the UK, regulators measure the WHOLE truck from front bumper to rear door."),
            ("इसलिए मालिकों को पीछे ज्यादा माल भरने के लिए केबिन को बिल्कुल चपटा करना पड़ता है।", "So every extra inch up front steals money-making cargo space in the back!"),
            ("और बेचारे ड्राइवर को सीधा गर्म इंजन के ऊपर अपनी सीट लगाकर बैठना पड़ता है!", "That's why the cab goes flat and the driver sits right on top of the hot engine!"),
            ("लेकिन अमेरिका में कानून सिर्फ पीछे के ट्रेलर की लंबाई गिनता है, आगे के केबिन की बिल्कुल नहीं!", "But in America, the law ONLY limits the trailer—the cab can be as long as you want!"),
            ("तो अमेरिकी कंपनियों ने इंजन आगे खिसका दिया और पीछे पूरा बेडरूम जैसा केबिन बना दिया...", "So US builders pushed the engine forward and added a literal bedroom inside..."),
            ("...जिससे हाईवे पर हवा भी कम टकराती है और मरम्मत भी आसान होती है, और यही वजह है कि...", "...making highway driving way smoother, which is the exact reason why..."),
        ],
    ),
    (
        "He Bought an Entire Bank for $1 Using a Dumb Loophole?! #Shorts",
        "Loophole Comedy",
        "tall_tale_3d",
        [
            ("भाई, निन्यानवे में एक बंदे ने पूरी की पूरी बैंक सिर्फ एक डॉलर में खरीद ली! क्या मज़ाक चल रहा है?!", "In 1999, some dude bought a WHOLE bank for one freakin' dollar—what the hell?!"),
            ("सच्ची बता रहा हूँ यार, वो बैंक इतना कंगाल हो चुका था कि कोई उसके पास भटकना भी नहीं चाहता था।", "Deadass, bro—that bank was so broke nobody wanted to touch that garbage."),
            ("सरकारी अफसर बस किसी भी तरह उस सिरदर्द को अपने सिर से टालना चाहते थे।", "Regulators were desperate to dump the headache on literally anyone with a pulse."),
            ("तभी ये शातिर दिमाग वाला बंदा सस्ता सूट पहनकर आया और मेज पर एक मुड़ा हुआ नोट पटक दिया।", "So this madman walks in wearing a cheap suit and slaps a crumpled buck on the table."),
            ("अफसरों को लगा ये बेवकूफ फंस गया, और उन्होंने तुरंत कागज़ पर साइन कर दिए!", "The officials thought THEY scammed him and signed the papers in ten seconds flat!"),
            ("पर असली खेल अब शुरू हुआ—उसने देखा कि बैंक की पुरानी ज़मीन ही करोड़ों की थी!", "Wait, it gets dumber—he noticed the bank's downtown land alone was worth MILLIONS."),
            ("उसने पीछे की पार्किंग बेचकर सारा पुराना कर्ज़ा एक झटके में साफ कर दिया...", "He flipped the back parking lot, wiped out every cent of debt overnight..."),
            ("...और पूरी बैंक मुफ्त में उसकी हो गई, और literally यही reason है कि...", "...and kept the entire bank for FREE, which is literally how in..."),
        ],
    ),
    (
        "Swallowing Gum Does WHAT Inside Your Stomach?! #Shorts",
        "Body Myth Buster",
        "deep_dive_3d",
        [
            ("बचपन में घरवालों ने डराया था कि च्युइंग गम निगली तो सात साल पेट में सड़ेगी! क्या बकवास था यार!", "Our parents swore swallowed gum stays in your gut for SEVEN years—what total crap!"),
            ("चलो आज पेट के अंदर ज़ूम करके देखते हैं कि असली में वहां क्या बवाल मचता है।", "Let's zoom inside your stomach right now to see the actual chaos."),
            ("जैसे ही गम नीचे गिरती है, पेट का खतरनाक एसिड उस पर टूट पड़ता है।", "The second that gum drops in, stomach acid blasts it at full power."),
            ("चीनी और मिंट का स्वाद तो दस मिनट में गायब हो जाता है, पर असली पंगा बेस रबर का है।", "The sugar and mint dissolve in minutes, but the synthetic rubber base refuses to die."),
            ("क्योंकि उस गम में वही सिंथेटिक पॉलिमर होता है जो कार के टायर बनाने में लगता है!", "Because gum base uses the same tough polymers found in literal car tires, bro!"),
            ("पर क्या वो आंतों की दीवार पर चिपकती है? बिल्कुल नहीं, वहां सब कुछ फिसलन भरा होता है।", "Does it stick to your stomach wall? Zero chance—your gut lining is slick as teflon."),
            ("तुम्हारे पेट की मांसपेशियां उसे बाकी खाने के साथ धक्का मारकर आगे भेज देती हैं...", "Your digestive muscles just bulldoze the blob straight down the pipeline..."),
            ("...और अड़तालीस घंटे में वो सीधा बाहर निकल जाती है, और यही पागल झूठ वजह है कि...", "...and yeet it out in 48 hours flat, which is the exact reason why..."),
        ],
    ),
    (
        "He Mailed Himself First-Class in a Box to Escape Prison?! #Shorts",
        "Crazy Breakout",
        "tall_tale_3d",
        [
            ("एक कैदी ने जेल से भागने के लिए सुरंग नहीं खोदी—भाई ने खुद को पार्सल डिब्बे में पैक करके कूरियर कर दिया!", "A prisoner didn't dig a tunnel to escape—bro literally mailed himself in a courier box!"),
            ("जर्मनी की हाई-सिक्योरिटी जेल में ये बंदा रोज़ चुपचाप डाक पैक करने का काम करता था।", "Locked inside a high-security prison, he worked the daily warehouse mail shift."),
            ("एक दिन उसने सबसे बड़ा गत्ते का डिब्बा उठाया और उस पर एक्सप्रेस डिलीवरी का स्टीकर चिपका दिया।", "One afternoon, he grabbed an oversized crate and slapped an Express Delivery label on it."),
            ("अंदर एक कंबल, पानी की बोतल और छोटा सा चाकू लेकर वो खुद डिब्बे में दुबक कर बैठ गया।", "He hopped inside with a blanket, a water bottle, and a tiny pocket knife."),
            ("उसके दोस्त ने बाहर से भूरा टेप लपेटा और गार्ड्स के सामने ही डिब्बा ट्रॉली पर रख दिया!", "His buddy taped the flaps shut and wheeled him right past the armed guards!"),
            ("गार्ड्स ने खुद अपने हाथों से उसका भारी डिब्बा उठाकर कूरियर ट्रक में लोड कर दिया, क्या कॉमेडी है!", "The guards even complained the box was heavy while loading him onto the truck!"),
            ("जैसे ही ट्रक जेल के गेट से दो किलोमीटर दूर निकला, उसने अंदर से गत्ता काटा और कूद गया...", "Two miles outside the prison gates, he sliced the cardboard open and hopped off..."),
            ("...ड्राइवर को पीछे खाली डिब्बा मिला जब तक वो गायब हो चुका था, और यही वजह है कि...", "...leaving the driver with an empty box, which is the exact reason why..."),
        ],
    ),
    (
        "How Pepsi Briefly Owned 17 Soviet Attack Submarines?! #Shorts",
        "Absurd History",
        "inside_out",
        [
            ("भाई, नवासी में कोल्ड-ड्रिंक बेचने वाली कंपनी Pepsi के पास अचानक सत्रह असली पनडुब्बियां और तीन जंगी जहाज आ गए!", "In 1989, a literal soda company suddenly owned 17 attack submarines and 3 warships!"),
            ("सुनने में मज़ाक लगता है यार, पर सोवियत संघ के लोगों को Pepsi की भयंकर लत लग चुकी थी।", "No joke, the Soviet Union was completely addicted to fizzy cola."),
            ("पंगा ये था कि रूसी रूबल की बाहर के देशों में कोई कीमत नहीं चलती थी।", "The problem? Soviet rubles were worthless outside the country, so they couldn't pay cash."),
            ("तो पैसे देने के बदले सरकार ने सीधा अपनी पुरानी नौसेना के हथियार टेबल पर रख दिए!", "So instead of money, the Kremlin paid their soda bill with literal military hardware!"),
            ("एक झटके में Pepsi दुनिया की छठी सबसे बड़ी मिलिट्री ताकत बन गई!", "Overnight, a soft-drink CEO commanded the 6th largest submarine fleet on Earth!"),
            ("अमेरिका के सुरक्षा अफसरों के पसीने छूट गए कि अब कोला वाले समंदर पर राज करेंगे क्या?!", "Pentagon officials panicked when they saw a beverage company flexing naval warships!"),
            ("तब Pepsi के बॉस ने हंसते हुए कहा—भाई हम सोवियत सेना को तुमसे तेज डिसआर्म कर रहे हैं...", "Pepsi's boss joked: Bro, we're disarming the Soviet Navy faster than the US government..."),
            ("...और फिर उन्होंने सारे जहाज कबाड़ में बेचकर अरबों कमा लिए, और यही वजह है कि...", "...before flipping the whole fleet for scrap metal cash, which is why..."),
        ],
    ),
    (
        "Why Airplane Windows Always Have That Tiny Creepy Hole?! #Shorts",
        "Everyday Science Comedy",
        "stick_story",
        [
            ("फ्लाइट में खिड़की के पास बैठकर जब उस छोटे से छेद को देखते हो, तो जान हलक में आ जाती है ना?!", "Sitting by an airplane window and spotting a hole in the glass feels terrifying, right?!"),
            ("भाई, पहली बार देखकर लगता है कि क्या प्लेन की खिड़की में किसी ने कील ठोक दी है?!", "First time you see it, you swear the cabin is about to depressurize mid-flight!"),
            ("पर सच ये है कि अगर वो नन्हा सा छेद वहां न हो, तो पूरी खिड़की धमाके के साथ फट सकती है!", "Truth is, without that tiny millimeter hole, the window could literally shatter at 35,000 feet!"),
            ("असली में प्लेन की खिड़की एक नहीं, बल्कि तीन अलग-अलग कांच की परतों से बनी होती है।", "Airplane windows actually have three separate layers of acrylic glass."),
            ("जब प्लेन ऊपर जाता है, तो बाहर हवा का दबाव गिर जाता है और अंदर का प्रेशर बहुत ज़्यादा होता है।", "Up in the sky, outside air pressure drops near zero while cabin pressure stays huge."),
            ("वो छोटा सा Bleed Hole बीच वाले कांच में होता है जो दोनों तरफ का प्रेशर बराबर रखता है!", "That bleed hole sits in the middle pane so the outer glass takes 100% of the load safely!"),
            ("साथ ही वो तुम्हारी सांस की भाप को भी कांच पर जमने से रोकता है...", "Plus it stops your breath from fogging or freezing the glass solid..."),
            ("...ताकि तुम बादलों की फोटो खींच सको और खिड़की सुरक्षित रहे, और यही वजह है कि...", "...keeping the window from exploding mid-air, which is literally why..."),
        ],
    ),
    (
        "How Australia Fought a War Against 20,000 Birds and LOST?! #Shorts",
        "History Roast",
        "tall_tale_3d",
        [
            ("भाई, बत्तीस में ऑस्ट्रेलिया की असली सेना ने बीस हज़ार पक्षियों के खिलाफ युद्ध छेड़ा—और सेना हार गई!", "In 1932, Australia sent the literal military to fight 20,000 flightless birds—and LOST!"),
            ("वहां के किसानों की फसल को बड़े-बड़े Emu पक्षी रोज़ चौपट कर रहे थे।", "Giant emus were stampeding through wheat farms like feathered bulldozers."),
            ("तो सरकार ने मदद के लिए सामान्य पुलिस नहीं, बल्कि मशीनगन वाली फौज भेज दी!", "So the government deployed soldiers armed with Lewis machine guns and 10,000 rounds!"),
            ("सैनिकों को लगा कि दो दिन में सारे पक्षियों का काम तमाम कर देंगे।", "The troops bragged they'd wrap up the bird war before lunchtime."),
            ("पर जैसे ही फायरिंग शुरू हुई, पक्षी छोटे-छोटे गुटों में बंटकर पचास की स्पीड से भागे!", "Instead, the emus split into guerrilla squads and sprinted at 30 miles per hour!"),
            ("यहां तक कि एक पक्षी को पांच गोलियां लगने के बाद भी वो जीप से तेज़ दौड़ रहा था!", "Even taking multiple hits, those birds outran the army trucks across bumpy fields!"),
            ("हज़ारों गोलियां फूंकने के बाद मेजर ने शर्म के मारे अपने हथियार डाल दिए...", "After burning thousands of bullets for almost nothing, the Major rage-quit and retreated..."),
            ("...और पक्षियों ने बिना एक भी हथियार चलाए युद्ध जीत लिया, और यही वजह है कि...", "...handing flightless birds an undefeated military record, which is why..."),
        ],
    ),
    (
        "Why Laxman's Wife Urmila Slept for 14 Years Straight?! #Shorts",
        "Mythology Secret",
        "night_file_3d",
        [
            ("रामायण में लक्ष्मण चौदह साल बिना सोए जागे रहे—पर क्या तुम्हें पता है उनके बदले कौन सोया था?!", "Laxman stayed awake for 14 years straight in exile—but do you know who slept in his place?!"),
            ("जब राम और सीता वनवास गए, तो लक्ष्मण ने कसम खाई कि वो चौदह साल एक पल भी पलक नहीं झपकाएंगे।", "On the first night in the forest, Laxman vowed to guard Ram and Sita without blinking."),
            ("तभी वहां निद्रा देवी प्रकट हुईं और बोलीं—प्रकृति का नियम है कि तुम्हारे हिस्से की नींद किसी को लेनी ही पड़ेगी!", "The Goddess of Sleep appeared and warned: Nature's law demands someone take your sleep!"),
            ("तब लक्ष्मण ने हाथ जोड़कर अपनी पत्नी उर्मिला का नाम लिया जो अयोध्या के महल में थीं।", "Laxman asked her to visit his wife Urmila back in the palace of Ayodhya."),
            ("उर्मिला ने बिना एक सवाल पूछे मुस्कुराकर लक्ष्मण के चौदह साल की नींद अपने सिर ले ली!", "Without a second of hesitation, Urmila accepted all 14 years of his exhaustion!"),
            ("क्योंकि मेघनाद को वरदान था कि उसे वही हरा सकता है जो चौदह साल से बिल्कुल न सोया हो!", "Because Meghnad held a boon that only a warrior awake for 14 years could defeat him!"),
            ("महल में उर्मिला की उस चुपचाप दी गई कुर्बानी ने ही लक्ष्मण को अजेय बनाया...", "Urmila's silent 14-year slumber in the palace gave Laxman the power to win the war..."),
            ("...और जब राम लौटे तब जाकर उर्मिला की आंखें खुलीं, और यही अनसुना सच वजह है कि...", "...waking up only on the day of coronation, which is the exact reason why..."),
        ],
    ),
]


def _load_used(base_dir: Path) -> list[str]:
    p = base_dir / "data" / "used_topics.json"
    if p.exists():
        try:
            return list(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            pass
    return []


def _save_used(base_dir: Path, used: list[str]) -> None:
    p = base_dir / "data" / "used_topics.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(used[-200:], indent=2), encoding="utf-8")


def generate_funny_story(
    base_dir: Path,
    spoken_lang: str = "hi",
    style_override: str | None = None,
    custom_topic: str | None = None,
) -> dict:
    used = _load_used(base_dir)
    if style_override in ("", "auto", None):
        style_override = None

    if custom_topic and custom_topic.strip():
        ct = custom_topic.strip()
        st = style_override or classify_reference_style(ct)
        raw_beats = [
            (f"Rohan: मीरा सुनो—आज मैंने {ct} के बारे में पढ़ा और मेरा दिमाग हिल गया है!", f"Rohan: Meera, wait—I just read the truth about {ct} and my brain is melting!"),
            (f"Meera: अच्छा? फिर से कोई आधी रात की ओवरथिंकिंग शुरू हो गई क्या? बताओ क्या कांड है!", f"Meera: Oh great, another 2 AM overthinking session? Tell me what's going on."),
            (f"Rohan: मज़ाक नहीं यार, बाहर से तो सबको लगता है कि {ct} बिल्कुल सामान्य सी बात है!", f"Rohan: Deadass, everyone assumes {ct} is completely normal on the surface!"),
            ("Meera: हां तो? मुझे भी यही लगता था। इसमें कौन सा बड़ा सीक्रेट छुपा है?", "Meera: Right, that's what everyone thinks. What's the hidden catch?"),
            (f"Rohan: असली पंगा ये है कि इसके पीछे एक इतना शातिर नियम काम करता है जो किसी को दिखता नहीं!", f"Rohan: The catch is a sneaky hidden rule running behind the scenes that nobody notices!"),
            ("Meera: रुको क्या?! मतलब इतने सालों से हम सब बेवकूफ बन रहे थे?!", "Meera: Wait WHAT?! You're telling me we've all been getting played this whole time?!"),
            ("Rohan: बिल्कुल! जैसे ही असली प्रेशर पड़ता है, पूरा खेल एक झटके में पलट जाता है...", "Rohan: Exactly! The second pressure hits, the whole setup flips upside down..."),
            ("Meera: ...और बिस्किट बिल्ली को भी ये बात हमसे पहले से पता थी, और यही वजह है कि...", "Meera: ...and even Biscuit the cat knew before us, which is the exact reason why..."),
        ]
        cat_label = "2D Sitcom Skit (Custom Topic)"
        title = f"{ct.rstrip('?!')}?! #Shorts"
    else:
        unseen = []
        for entry in COMEDY_STORIES:
            h = hashlib.md5(entry[0].encode("utf-8")).hexdigest()[:10]
            if h not in used:
                unseen.append((h, entry))
        if not unseen:
            used = []
            unseen = [(hashlib.md5(e[0].encode("utf-8")).hexdigest()[:10], e) for e in COMEDY_STORIES]

        chosen_hash, chosen = random.choice(unseen)
        used.append(chosen_hash)
        _save_used(base_dir, used)
        title, cat_label, default_style, raw_beats = chosen
        st = style_override or default_style

    beats = []
    for i, (hi_txt, en_txt) in enumerate(raw_beats, start=1):
        if spoken_lang == "hi":
            spoken = hi_txt
        elif spoken_lang == "en":
            spoken = en_txt
        else:
            spoken = translate_text(en_txt, spoken_lang)
        beats.append({
            "beat_id": i,
            "spoken_text": spoken,
            "hi_spoken_text": hi_txt,
            "en_subtitle": en_txt,
            "character_expression": EXPRESSIONS[i - 1],
            "character_pose": POSES[i - 1],
            "camera_action": CAMERAS[i - 1],
            "prop": "FACT",
            "sfx_cue": SFX_SEQ[i - 1],
        })

    story_dict = {
        "title": title,
        "source": f"Comedy Vault · {cat_label}",
        "source_url": "",
        "style": st,
        "spoken_language": spoken_lang,
        "hook_score": round(random.uniform(9.5, 9.9), 1),
        "loop_bridge": "...which is literally why",
        "beats": beats,
    }
    return scene_planner.plan_story_scenes(story_dict)


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    print(json.dumps(generate_funny_story(root, "hi"), indent=2, ensure_ascii=False))
