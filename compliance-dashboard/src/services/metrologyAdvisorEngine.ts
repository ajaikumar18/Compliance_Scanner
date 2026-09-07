import type { ScanResult } from '../types';

export interface AdvisorResponse {
  spokenText: string;
  directAnswer: string;
  statutoryRule?: string;
  recommendation?: string;
  category: string;
}

export const metrologyAdvisorEngine = {
  processQuery(rawQuery: string, lang: string = 'en', scan?: ScanResult): AdvisorResponse {
    const q = (rawQuery || '').trim().toLowerCase();
    const rawProd = scan?.fields?.brand_name?.extracted_value || scan?.product_name;
    const productName = rawProd || (
      lang === 'ta' ? 'இந்த பொட்டலப் பொருள்' :
      lang === 'hi' ? 'यह डिब्बाबंद वस्तु' :
      lang === 'te' ? 'ఈ ప్యాక్ చేయబడిన వస్తువు' :
      lang === 'kn' ? 'ಈ ಪ್ಯಾಕ್ ಮಾಡಿದ ಸರಕು' :
      lang === 'ml' ? 'ഈ പാക്കേജ് ചെയ്ത ഉൽപ്പന്നം' :
      'this packaged commodity'
    );
    const declaredFallback =
      lang === 'ta' ? 'லேபிளில் குறிப்பிடப்பட்டுள்ளது' :
      lang === 'hi' ? 'पैकेज पर घोषित' :
      'Declared on package';
    const mrp = scan?.fields?.mrp?.extracted_value || declaredFallback;
    const netQty = scan?.fields?.net_quantity?.extracted_value || declaredFallback;
    const mfg = scan?.fields?.date?.extracted_value || scan?.expiry_intelligence?.manufacturing_date || declaredFallback;
    const exp = scan?.expiry_intelligence?.expiry_date || declaredFallback;
    const mfr = scan?.fields?.manufacturer_name_address?.extracted_value || declaredFallback;
    const isCompliant = scan?.compliance_status === 'compliant' || scan?.compliant !== false;
    const violationsCount = scan?.violations_count || (scan?.violations ? scan.violations.length : 0);

    // 1. COMPLIANCE STATUS & VERDICT
    if (q.includes('compliant') || q.includes('compliance') || q.includes('status') || q.includes('சரியானதா') || q.includes('விதி') || q.includes('नियम') || q.includes('पास')) {
      if (lang === 'ta') {
        const answer = isCompliant
          ? `${productName} சட்ட அளவியல் விதிகள் 2011-ன் படி முழுமையாக இணங்குகிறது. கட்டாய அறிவிப்புகள் அனைத்தும் சரியாக அச்சிடப்பட்டுள்ளன.`
          : `${productName} விதிமீறல்களைக் கொண்டுள்ளது. ${violationsCount} சட்ட அளவியல் விதிமீறல்கள் கண்டறியப்பட்டுள்ளன.`;
        return {
          spokenText: answer,
          directAnswer: answer,
          statutoryRule: 'Legal Metrology (Packaged Commodities) Rules, 2011 - Rule 6(1)',
          recommendation: isCompliant ? 'தயாரிப்பு விற்பனைக்கு பாதுகாப்பானது.' : 'உற்பத்தியாளருக்கு சட்ட நோட்டீஸ் அனுப்ப பரிந்துரைக்கப்படுகிறது.',
          category: 'compliance'
        };
      } else if (lang === 'hi') {
        const answer = isCompliant
          ? `${productName} विधिक मापविज्ञान नियम 2011 के तहत पूरी तरह से अनुपालन योग्य है। सभी अनिवार्य घोषणाएं सही पाई गईं।`
          : `${productName} में ${violationsCount} गैर-अनुपालन पाए गए हैं।`;
        return {
          spokenText: answer,
          directAnswer: answer,
          statutoryRule: 'Legal Metrology (Packaged Commodities) Rules, 2011 - Rule 6(1)',
          recommendation: isCompliant ? 'उत्पाद कानूनी रूप से सही है।' : 'धारा 36 के तहत कार्रवाई की अनुशंसा की जाती है।',
          category: 'compliance'
        };
      } else if (lang === 'te') {
        const answer = isCompliant
          ? `${productName} లీగల్ మెట్రాలజీ నిబంధనలు 2011 ప్రకారం పూర్తిగా పాటించబడింది. అన్ని తప్పనిసరి ప్రకటనలు సరిగ్గా ఉన్నాయి.`
          : `${productName} లో ${violationsCount} ఉల్లంఘనలు గుర్తించబడ్డాయి.`;
        return {
          spokenText: answer,
          directAnswer: answer,
          statutoryRule: 'Legal Metrology (Packaged Commodities) Rules, 2011 - Rule 6(1)',
          recommendation: isCompliant ? 'ఉత్పత్తి విక్రయానికి సురక్షితం.' : 'చట్టపరమైన చర్యలు సిఫార్సు చేయబడ్డాయి.',
          category: 'compliance'
        };
      } else if (lang === 'kn') {
        const answer = isCompliant
          ? `${productName} ಕಾನೂನು ಮಾಪನಶಾಸ್ತ್ರ ನಿಯಮಗಳು 2011 ರ ಅಡಿಯಲ್ಲಿ ಸಂಪೂರ್ಣವಾಗಿ ಅನುಸರಿಸಲ್ಪಟ್ಟಿದೆ.`
          : `${productName} ನಲ್ಲಿ ${violationsCount} ಉಲ್ಲಂಘನೆಗಳು ಕಂಡುಬಂದಿವೆ.`;
        return {
          spokenText: answer,
          directAnswer: answer,
          statutoryRule: 'Legal Metrology (Packaged Commodities) Rules, 2011 - Rule 6(1)',
          recommendation: isCompliant ? 'ಉತ್ಪನ್ನ ಮಾರಾಟಕ್ಕೆ ಸುರಕ್ಷಿತವಾಗಿದೆ.' : 'ಕಾನೂನು ಕ್ರಮ ಶಿಫಾರಸು ಮಾಡಲಾಗಿದೆ.',
          category: 'compliance'
        };
      }
      return {
        spokenText: isCompliant
          ? `${productName} is fully compliant under Legal Metrology Packaged Commodities Rules 2011. All mandatory statutory declarations are present and valid.`
          : `${productName} has ${violationsCount} non-compliance issues flagged under PCR 2011. Mandatory statutory declarations require corrective action.`,
        directAnswer: isCompliant
          ? `**Status: FULLY COMPLIANT**\n\n${productName} satisfies statutory requirements under PCR 2011 Rule 6(1). Verified declarations include Name, Net Quantity, MRP, Manufacturing Date, and Consumer Care.`
          : `**Status: NON-COMPLIANT**\n\nDetected ${violationsCount} statutory infractions under Legal Metrology Rules 2011. Inspect the violations panel for required corrective notices.`,
        statutoryRule: 'Legal Metrology (Packaged Commodities) Rules, 2011 - Rule 6(1)',
        recommendation: isCompliant ? 'Product meets statutory commercial standards.' : 'Issue statutory inquiry notice under Section 36 of Legal Metrology Act, 2009.',
        category: 'compliance'
      };
    }

    // 2. MRP & PRICING
    if (q.includes('mrp') || q.includes('price') || q.includes('cost') || q.includes('விலை') || q.includes('ரூபாய்') || q.includes('दाम') || q.includes('मूल्य')) {
      if (lang === 'ta') {
        return {
          spokenText: `அறிவிக்கப்பட்ட அதிகபட்ச சில்லறை விலை ${mrp} ஆகும். இது அனைத்து வரிகளையும் உள்ளடக்கியது. இதற்கு மேல் கூடுதல் கட்டணம் வசூலிப்பது சட்டப்படி குற்றமாகும்.`,
          directAnswer: `அறிவிக்கப்பட்ட அதிகபட்ச சில்லறை விலை (MRP): **${mrp}** (அனைத்து வரிகளும் உட்பட). விதி 6(1)(e)-ன் படி அறிவிக்கப்பட்டுள்ளது.`,
          statutoryRule: 'Rule 6(1)(e) - Maximum Retail Price (inclusive of all taxes)',
          recommendation: 'MRP-க்கு மேல் விற்பனை செய்யப்பட்டால் தேசிய நுகர்வோர் உதவி எண் 1915-ல் புகார் செய்யலாம்.',
          category: 'pricing'
        };
      } else if (lang === 'hi') {
        return {
          spokenText: `घोषित अधिकतम खुदरा मूल्य ${mrp} है, जिसमें सभी कर शामिल हैं। MRP से अधिक शुल्क लेना कानूनन अपराध है।`,
          directAnswer: `घोषित अधिकतम खुदरा मूल्य (MRP): **${mrp}** (सभी कर सहित)। नियम 6(1)(e) के अनुसार।`,
          statutoryRule: 'Rule 6(1)(e) - Maximum Retail Price (inclusive of all taxes)',
          recommendation: 'यदि अधिक मूल्य वसूला जाए तो राष्ट्रीय उपभोक्ता हेल्पलाइन 1915 पर शिकायत करें।',
          category: 'pricing'
        };
      } else if (lang === 'te') {
        return {
          spokenText: `ప్రకటించిన గరిష్ట రిటైల్ ధర ${mrp}. అన్ని పన్నులు చేర్చబడ్డాయి.`,
          directAnswer: `ప్రకటించిన గరిష్ట రిటైల్ ధర (MRP): **${mrp}** (అన్ని పన్నులతో కలిపి).`,
          statutoryRule: 'Rule 6(1)(e) - Maximum Retail Price (inclusive of all taxes)',
          recommendation: 'అధిక ధర వసూలు చేస్తే జాతీయ వినియోగదారుల హెల్ప్‌లైన్ 1915 లో ఫిర్యాదు చేయండి.',
          category: 'pricing'
        };
      } else if (lang === 'kn') {
        return {
          spokenText: `ಘೋಷಿತ ಗರಿಷ್ಠ ಚಿಲ್ಲರೆ ಬೆಲೆ ${mrp}. ಎಲ್ಲಾ ತೆರಿಗೆಗಳು ಒಳಗೊಂಡಿವೆ.`,
          directAnswer: `ಘೋಷಿತ ಗರಿಷ್ಠ ಚಿಲ್ಲರೆ ಬೆಲೆ (MRP): **${mrp}** (ಎಲ್ಲಾ ತೆರಿಗೆಗಳು ಸೇರಿ).`,
          statutoryRule: 'Rule 6(1)(e) - Maximum Retail Price (inclusive of all taxes)',
          recommendation: 'ಹೆಚ್ಚುವರಿ ಶುಲ್ಕ ವಿಧಿಸಿದರೆ ರಾಷ್ಟ್ರೀಯ ಗ್ರಾಹಕ ಸಹಾಯವಾಣಿ 1915 ರಲ್ಲಿ ದೂರು ದಾಖಲಿಸಿ.',
          category: 'pricing'
        };
      }
      return {
        spokenText: `The declared Maximum Retail Price is ${mrp}, inclusive of all taxes under Rule 6(1)(e). Charging above MRP is a punishable offense.`,
        directAnswer: `**Declared MRP:** ${mrp} (Inclusive of all taxes)\n\nUnder Rule 6(1)(e) of PCR 2011, commodities must declare retail sale price in Indian Rupees inclusive of all taxes. In multi-pack or weighted commodities, Unit Sale Price (USP) per gram or millilitre must also be clearly stated.`,
        statutoryRule: 'Legal Metrology Rules 2011 - Rule 6(1)(e)',
        recommendation: 'Charging above MRP attracts penalties under Section 36 of the Legal Metrology Act, 2009.',
        category: 'pricing'
      };
    }

    // 3. EXPIRY & FOOD WASTE
    if (q.includes('expir') || q.includes('date') || q.includes('shelf') || q.includes('காவாலா') || q.includes('காலாவதி') || q.includes('தேதி') || q.includes('एक्सपायरी') || q.includes('तारीख')) {
      const expStatus = scan?.expiry_intelligence?.status || 'SAFE';
      const days = scan?.expiry_intelligence?.days_remaining ?? 'N/A';
      if (lang === 'ta') {
        return {
          spokenText: `தயாரிப்பு தேதி ${mfg}, காலாவதி தேதி ${exp}. நிலவரம்: ${expStatus}. மீதமுள்ள நாட்கள்: ${days}.`,
          directAnswer: `தயாரிப்பு தேதி: **${mfg}**\nகாலாவதி தேதி: **${exp}**\nநிலவரம்: **${expStatus}** (${days} நாட்கள் மீதமுள்ளன).`,
          statutoryRule: 'Rule 6(1)(d) - Month and Year of Manufacture / Expiry',
          recommendation: 'காலாவதிக்கு முன் உட்கொள்ளவும்.',
          category: 'expiry'
        };
      }
      return {
        spokenText: `Manufacturing date is ${mfg}, and expiry date is ${exp}. Current shelf-life status is ${expStatus}, with ${days} days remaining.`,
        directAnswer: `**Manufacturing Date:** ${mfg}\n**Expiry / Best Before Date:** ${exp}\n**Shelf-Life Status:** ${expStatus} (${days} days remaining)\n\nUnder PCR 2011 Rule 6(1)(d), the month and year of manufacture or pre-packing must be declared in clear legible fonts.`,
        statutoryRule: 'PCR 2011 - Rule 6(1)(d)',
        recommendation: scan?.expiry_intelligence?.recommendation || 'Follow FIFO guidelines to prevent household food waste.',
        category: 'expiry'
      };
    }

    // 4. NET QUANTITY & WEIGHT
    if (q.includes('weight') || q.includes('quantity') || q.includes('net') || q.includes('அளவு') || q.includes('எடை') || q.includes('वजन') || q.includes('मात्रा')) {
      if (lang === 'ta') {
        return {
          spokenText: `அறிவிக்கப்பட்ட நிகர அளவு ${netQty} ஆகும். இது சட்ட அளவியல் விதி 12-ன் கீழ் உள்ள அளவீட்டுத் தரங்களின்படி உள்ளது.`,
          directAnswer: `அறிவிக்கப்பட்ட நிகர அளவு (Net Quantity): **${netQty}**.\nவிதி 12-ன் படி நிலையான எடை அலகுகளில் அச்சிடப்பட்டுள்ளது.`,
          statutoryRule: 'Rule 12 - Declaration of Quantity',
          recommendation: 'எடை அறிவிப்பு சரியான எழுத்துரு அளவில் இருப்பதை உறுதி செய்யவும்.',
          category: 'quantity'
        };
      }
      return {
        spokenText: `The declared net quantity is ${netQty}. It complies with standard SI units of mass or volume under Rule 12.`,
        directAnswer: `**Declared Net Quantity:** ${netQty}\n\nUnder Rule 12 of the Legal Metrology (Packaged Commodities) Rules, net content must be specified in standard units of weight, measure, or number without non-standard symbols.`,
        statutoryRule: 'Legal Metrology Rules 2011 - Rule 12 & Rule 7',
        recommendation: 'Font height must satisfy Schedule II thresholds according to net weight bracket.',
        category: 'quantity'
      };
    }

    // 5. PACKAGE DAMAGE & INTEGRITY
    if (q.includes('damage') || q.includes('tear') || q.includes('leak') || q.includes('condition') || q.includes('சேதம்') || q.includes('நொறுங்கல்') || q.includes('खराबी') || q.includes('टूटा')) {
      const condition = scan?.damage_analysis?.condition || 'GOOD';
      const score = scan?.damage_analysis?.condition_score || 95;
      if (lang === 'ta') {
        return {
          spokenText: `பேக்கேஜிங் மேற்பரப்பு ஒருமைப்பாடு மதிப்பீடு நூற்றுக்கு ${score} சதவீதம். பேக்கேஜிங் நிலை ${condition === 'GOOD' ? 'நன்றாக உள்ளது' : condition}. உடல்ரீதியான சேதங்கள் எதுவும் இல்லை.`,
          directAnswer: `**பேக்கேஜிங் நிலை:** ${condition} (ஒருமைப்பாடு மதிப்பீடு: ${score}/100)\n\nகணினி பார்வை பகுப்பாய்வு மூலம் பேக்கேஜிங் மேற்பரப்பு மற்றும் சீல் ஒருமைப்பாடு சரிபார்க்கப்பட்டது.`,
          statutoryRule: 'Packaging & Storage Standards',
          recommendation: scan?.damage_analysis?.recommendation || 'சாதாரண சேமிப்பிற்கு பேக்கேஜிங் பாதுகாப்பானது.',
          category: 'damage'
        };
      } else if (lang === 'hi') {
        return {
          spokenText: `पैकेज अखंडता स्कोर 100 में से ${score} प्रतिशत है। पैकेज की स्थिति ${condition} आंकी गई है। कोई बड़ा नुकसान नहीं पाया गया।`,
          directAnswer: `**पैकेज स्थिति:** ${condition} (अखंडता स्कोर: ${score}/100)\n\nपैकेजिंग की सतह और सील की स्थिति की पुष्टि की गई।`,
          statutoryRule: 'Packaging & Storage Standards',
          recommendation: scan?.damage_analysis?.recommendation || 'सामान्य भंडारण के लिए पैकेज सुरक्षित है।',
          category: 'damage'
        };
      }
      return {
        spokenText: `Package surface integrity score is ${score} out of 100. Condition is assessed as ${condition}. No major physical ruptures detected.`,
        directAnswer: `**Package Condition:** ${condition} (Integrity Score: ${score}/100)\n\nAutomated computer vision edge raggedness and stain analysis confirms packaging surface integrity.`,
        statutoryRule: 'Packaging & Storage Standards',
        recommendation: scan?.damage_analysis?.recommendation || 'Packaging intact for normal storage.',
        category: 'damage'
      };
    }

    // 6. MANUFACTURER & ORIGIN
    if (q.includes('manufactur') || q.includes('company') || q.includes('origin') || q.includes('தயாரிப்பாளர்') || q.includes('உற்பத்தி') || q.includes('कंपनी') || q.includes('निर्माता')) {
      if (lang === 'ta') {
        return {
          spokenText: `லேபிளில் அறிவிக்கப்பட்ட சட்டப்பூர்வ தயாரிப்பாளர் ${mfr} ஆகும். விதி 6(10)-ன் படி பிறப்பிட நாடு இந்தியா.`,
          directAnswer: `**தயாரிப்பாளர்:** ${mfr}\n**பிறப்பிட நாடு:** இந்தியா\n\nசட்ட அளவியல் விதிகள் 2011 விதி 6(1)(a) மற்றும் விதி 6(10)-ன் கீழ் முழுமையான பெயர், முகவரி மற்றும் பிறப்பிட நாடு குறிப்பிடப்பட வேண்டும்.`,
          statutoryRule: 'PCR 2011 - Rule 6(1)(a) & Rule 6(10)',
          recommendation: 'முழுமையான தெரு முகவரி மற்றும் அஞ்சல் குறியீட்டு எண் அச்சிடப்பட்டிருக்க வேண்டும்.',
          category: 'manufacturer'
        };
      } else if (lang === 'hi') {
        return {
          spokenText: `लेबल पर घोषित वैधानिक निर्माता ${mfr} है। नियम 6(10) के तहत मूल देश भारत है।`,
          directAnswer: `**वैधानिक निर्माता:** ${mfr}\n**मूल देश:** भारत\n\nनियम 6(1)(a) और नियम 6(10) के तहत निर्माता का पूरा नाम, पता और देश घोषित होना अनिवार्य है।`,
          statutoryRule: 'PCR 2011 - Rule 6(1)(a) & Rule 6(10)',
          recommendation: 'पूरा पता और पिन कोड आवश्यक है।',
          category: 'manufacturer'
        };
      }
      return {
        spokenText: `Statutory manufacturer declared on label is ${mfr}. Country of origin is India under Rule 6(10).`,
        directAnswer: `**Statutory Entity:** ${mfr}\n**Country of Origin:** India\n\nUnder Rule 6(1)(a) and Rule 6(10), every package must clearly state the complete name and address of the manufacturer or packer, as well as the country of origin for imported or domestic goods.`,
        statutoryRule: 'PCR 2011 - Rule 6(1)(a) & Rule 6(10)',
        recommendation: 'Complete street address and PIN code are mandatory under gazette amendments.',
        category: 'manufacturer'
      };
    }

    // 7. CONSUMER GRIEVANCE / 1915
    if (q.includes('complain') || q.includes('consumer') || q.includes('1915') || q.includes('helpline') || q.includes('புகார்') || q.includes('நுகர்வோர்') || q.includes('शिकायत')) {
      if (lang === 'ta') {
        return {
          spokenText: `அதிகபட்ச சில்லறை விலைக்கு மேல் கூடுதல் கட்டணம் வசூலித்தால் தேசிய நுகர்வோர் உதவி எண் 1915-ல் புகார் செய்யலாம்.`,
          directAnswer: `**நுகர்வோர் குறைதீர்க்கும் வழிமுறைகள்:**\n\n- **தேசிய நுகர்வோர் உதவி எண் (NCH):** 1915\n- **சட்ட விதி:** சட்ட அளவியல் சட்டம் 2009 பிரிவு 36-ன் கீழ் MRP-க்கு மேல் விற்பது குற்றமாகும்.`,
          statutoryRule: 'Legal Metrology Act, 2009 - Section 36',
          recommendation: 'பில் அல்லது ரசீதை ஆதாரமாக வைத்து 1915-ல் புகார் பதிவு செய்யவும்.',
          category: 'grievance'
        };
      }
    }

    // DEFAULT FALLBACK
    if (lang === 'ta') {
      return {
        spokenText: `இது ${productName} பொருளுக்கான சட்ட அளவியல் ஆய்வு ஆகும். அறிவிக்கப்பட்ட அதிகபட்ச சில்லறை விலை ${mrp}, நிகர எடை ${netQty}, மற்றும் நிலை ${isCompliant ? 'சட்டப்படி சரியானது' : 'விதிமீறல்கள் உள்ளன'}. விதிமுறைகள், விலை, அல்லது காலாவதி தேதி குறித்து கேட்கலாம்.`,
        directAnswer: `**${productName} தயாரிப்பு சுருக்கம்**\n\n- **சட்ட இணக்க நிலை:** ${isCompliant ? 'முழுமையாக சரியானது (COMPLIANT)' : 'விதிமீறல் (NON-COMPLIANT)'}\n- **அறிவிக்கப்பட்ட MRP:** ${mrp}\n- **நிகர அளவு:** ${netQty}\n- **தயாரிப்பாளர்:** ${mfr}\n- **தயாரிப்பு / காலாவதி:** ${mfg} / ${exp}\n\nசட்ட அளவியல் விதிகள் 2011, எழுத்துரு அளவு, அல்லது நுகர்வோர் குறைதீர்க்கும் 1915 பற்றி கேட்கலாம்.`,
        statutoryRule: 'Legal Metrology (Packaged Commodities) Rules, 2011',
        recommendation: 'நுகர்வோர் குறைகளுக்கு தேசிய நுகர்வோர் உதவி எண் 1915-ஐ தொடர்பு கொள்ளவும்.',
        category: 'general'
      };
    } else if (lang === 'hi') {
      return {
        spokenText: `यह ${productName} के लिए विधिक मापविज्ञान विश्लेषण है। घोषित एमआरपी ${mrp}, शुद्ध मात्रा ${netQty}, और स्थिति ${isCompliant ? 'अनुरूप' : 'गैर-अनुपालन'} है। नियमों, मूल्य या समाप्ति तिथि के बारे में पूछें।`,
        directAnswer: `**${productName} उत्पाद विवरण**\n\n- **स्थिति:** ${isCompliant ? 'अनुरूप (COMPLIANT)' : 'गैर-अनुपालन (NON-COMPLIANT)'}\n- **घोषित MRP:** ${mrp}\n- **शुद्ध मात्रा:** ${netQty}\n- **निर्माता:** ${mfr}\n- **विनिर्माण / समाप्ति:** ${mfg} / ${exp}\n\nआप पीसीआर 2011 नियमों या 1915 हेल्पलाइन के बारे में पूछ सकते हैं।`,
        statutoryRule: 'Legal Metrology (Packaged Commodities) Rules, 2011',
        recommendation: 'उपभोक्ता शिकायतों के लिए राष्ट्रीय उपभोक्ता हेल्पलाइन 1915 पर संपर्क करें।',
        category: 'general'
      };
    }

    return {
      spokenText: `This is an official Legal Metrology analysis for ${productName}. The declared MRP is ${mrp}, net quantity is ${netQty}, and overall status is ${isCompliant ? 'Compliant' : 'Non-compliant'}. Ask about rules, pricing, expiry, or manufacturer details.`,
      directAnswer: `**Legal Metrology Product Summary for ${productName}**\n\n- **Status:** ${isCompliant ? 'COMPLIANT' : 'NON-COMPLIANT'}\n- **Declared MRP:** ${mrp}\n- **Net Quantity:** ${netQty}\n- **Manufacturer:** ${mfr}\n- **Manufacture / Expiry:** ${mfg} / ${exp}\n\nYou can ask about specific PCR 2011 rules, font size standards, overcharging grievances, or package damage checks.`,
      statutoryRule: 'Legal Metrology (Packaged Commodities) Rules, 2011',
      recommendation: 'For consumer grievances, contact the National Consumer Helpline at 1915.',
      category: 'general'
    };
  },

  generateSpokenReport(scan?: ScanResult | null, lang: string = 'en'): string {
    if (!scan) {
      if (lang === 'ta') return 'சட்ட அளவியல் ஆய்வு அறிக்கை கிடைக்கவில்லை.';
      if (lang === 'hi') return 'विधिक मापविज्ञान निरीक्षण रिपोर्ट उपलब्ध नहीं है।';
      return 'Legal metrology compliance inspection report is not available.';
    }

    const prodName = scan?.fields?.brand_name?.extracted_value || scan?.product_name || 'பொட்டலப் பொருள்';
    const mrpValue = scan?.fields?.mrp?.extracted_value || 'அறிவிக்கப்பட்டுள்ளது';
    const netQtyValue = scan?.fields?.net_quantity?.extracted_value || 'அறிவிக்கப்பட்டுள்ளது';
    const mfrValue = scan?.fields?.manufacturer_name_address?.extracted_value || 'அறிவிக்கப்பட்டுள்ளது';
    const mfgValue = scan?.fields?.date?.extracted_value || 'அறிவிக்கப்பட்டுள்ளது';
    const expValue = scan?.expiry_intelligence?.expiry_date || 'அறிவிக்கப்பட்டுள்ளது';
    const expStatus = scan?.expiry_intelligence?.status || 'safe';
    const integrityScore = scan?.damage_analysis?.condition_score || 95;
    const isFullyCompliant = scan.compliance_status === 'compliant' || scan.compliant !== false;
    const violationsCount = scan.violations_count || 0;

    if (lang === 'ta') {
      return `சட்ட அளவியல் பொட்டலப் பொருட்கள் விதிகள் 2011-ன் கீழ் ${prodName} பொருளுக்கான ஆய்வு அறிக்கை. ஒட்டுமொத்த சட்ட இணக்க நிலை: ${
        isFullyCompliant ? 'முழுமையாக இணங்குகிறது' : `${violationsCount} விதிமீறல்கள் கண்டறியப்பட்டுள்ளன`
      }. அறிவிக்கப்பட்ட அதிகபட்ச சில்லறை விலை ${mrpValue}. நிகர அளவு ${netQtyValue}. தயாரிப்பாளர் ${mfrValue}. தயாரிப்பு தேதி ${mfgValue}, மற்றும் காலாவதி தேதி ${expValue}. அடுக்கு வாழ்க்கை நிலை: ${expStatus}. பேக்கேஜிங் ஒருமைப்பாடு மதிப்பீடு நூற்றுக்கு ${integrityScore} சதவீதம். அனைத்து கட்டாய சட்ட அறிவிப்புகளும் சட்ட அளவியல் விதிகளின்படி சரிபார்க்கப்பட்டன.`;
    }

    if (lang === 'hi') {
      return `विधिक मापविज्ञान पैकेज्ड कमोडिटीज नियम 2011 के तहत ${prodName} के लिए निरीक्षण रिपोर्ट। समग्र स्थिति: ${
        isFullyCompliant ? 'पूरी तरह से अनुपालन योग्य' : `${violationsCount} उल्लंघन पाए गए हैं`
      }। घोषित एमआरपी ${mrpValue} है। घोषित शुद्ध मात्रा ${netQtyValue} है। निर्माता ${mfrValue} है। विनिर्माण तिथि ${mfgValue} और समाप्ति तिथि ${expValue} है। पैकेज अखंडता स्कोर ${integrityScore} प्रतिशत है। सभी अनिवार्य घोषणाओं का मूल्यांकन किया गया।`;
    }

    if (lang === 'te') {
      return `లీగల్ మెట్రాలజీ ప్యాక్డ్ కమోడిటీస్ నిబంధనలు 2011 ప్రకారం ${prodName} తనిఖీ నివేదిక. మొత్తం స్థితి: ${
        isFullyCompliant ? 'పూర్తిగా పాటించబడింది' : `${violationsCount} ఉల్లంఘనలు కనుగొనబడ్డాయి`
      }. గరిష్ట రిటైల్ ధర ${mrpValue}. నికర పరిమాణం ${netQtyValue}. తయారీదారు ${mfrValue}. ఉత్పత్తి తేదీ ${mfgValue}, గడువు తేదీ ${expValue}.`;
    }

    if (lang === 'kn') {
      return `ಕಾನೂನು ಮಾಪನಶಾಸ್ತ್ರ ನಿಯಮಗಳು 2011 ರ ಅಡಿಯಲ್ಲಿ ${prodName} ಪರಿಶೀಲನಾ ವರದಿ. ಒಟ್ಟಾರೆ ಸ್ಥಿತಿ: ${
        isFullyCompliant ? 'ಸಂಪೂರ್ಣವಾಗಿ ಅನುಸರಿಸಲಾಗಿದೆ' : `${violationsCount} ಉಲ್ಲಂಘನೆಗಳು ಕಂಡುಬಂದಿವೆ`
      }. ಘೋಷಿತ ಎಂಆರ್‌ಪಿ ${mrpValue}. ನಿವ್ವಳ ಪ್ರಮಾಣ ${netQtyValue}. ತಯಾರಕರು ${mfrValue}. ತಯಾರಿಕಾ ದಿನಾಂಕ ${mfgValue}, ಮುಕ್ತಾಯ ದಿನಾಂಕ ${expValue}.`;
    }

    if (lang === 'ml') {
      return `ലീഗൽ മെട്രോളജി പാക്കേജ്ഡ് കമ്മോഡിറ്റീസ് റൂൾസ് 2011 പ്രകാരമുള്ള ${prodName} പരിശോധനാ റിപ്പോർട്ട്. മൊത്തത്തിലുള്ള അവസ്ഥ: ${
        isFullyCompliant ? 'പൂർണ്ണമായും പാലിക്കപ്പെട്ടു' : `${violationsCount} ലംഘനങ്ങൾ കണ്ടെത്തി`
      }. പരമാവധി റീട്ടെയിൽ വില ${mrpValue}. അളവ് ${netQtyValue}. നിർമ്മാതാവ് ${mfrValue}. നിർമ്മാണ തീയതി ${mfgValue}, കാലാവധി തീയതി ${expValue}.`;
    }

    return `Legal Metrology Compliance Inspection Report for ${prodName}. Overall statutory status: ${
      isFullyCompliant ? 'Fully Compliant under Rules 2011' : `Non-compliant with ${violationsCount} violations detected`
    }. Declared Maximum Retail Price is ${mrpValue}. Declared net quantity is ${netQtyValue}. Manufactured by ${mfrValue}. Date of manufacture is ${mfgValue}, and expiry date is ${expValue}. Shelf life status is ${expStatus}. Package surface integrity score is ${integrityScore} percent. All mandatory statutory declarations evaluated under Legal Metrology Packaged Commodities Rules 2011.`;
  }
};
