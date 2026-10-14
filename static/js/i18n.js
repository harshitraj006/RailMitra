/**
 * RailMitra Internationalization (i18n) Engine.
 * Supports English (en), Hindi (hi), and Kannada (kn) for all static UI labels.
 * Station codes and berth numbers are kept untouched as per requirements.
 */

const translations = {
  en: {
    app_title: "RailMitra",
    app_subtitle: "Smart Railway Seat Exchange & Family Seating System",
    prototype_badge: "Prototype",
    demo_mode_banner: "DEMO MODE ACTIVE: Simulated reservation data. SMS/Email OTP printed below.",
    
    // Auth & Login
    login_title: "Passenger Login",
    login_subtitle: "Enter your simulated journey details to request or manage seat exchanges",
    pnr_label: "10-Digit PNR",
    pnr_placeholder: "e.g. PNR1000001",
    train_label: "Train Number",
    train_placeholder: "e.g. 12951",
    date_label: "Journey Date",
    date_placeholder: "YYYY-MM-DD",
    btn_validate: "Validate Journey",
    otp_title: "OTP Verification",
    otp_subtitle: "Enter the 6-digit code sent to your simulated mobile number",
    otp_label: "Verification Code (OTP)",
    otp_placeholder: "6-digit OTP",
    btn_verify: "Verify & Enter",
    btn_resend_otp: "Resend Code",
    btn_logout: "Sign Out",
    lockout_warning: "Account temporarily locked due to 3 failed attempts. Try again in:",
    seconds: "seconds",

    // Navigation & Tabs
    tab_home: "Journey Home",
    tab_find_matches: "Find Seat Exchange",
    tab_my_requests: "My Requests",
    tab_incoming: "Incoming Requests",
    tab_group_request: "Family Group",
    tab_notifications: "Notifications",

    // Journey Home
    journey_summary: "Your Journey Summary",
    passenger: "Passenger",
    berth_assigned: "Current Berth",
    route_segment: "Your Route",
    quota_badge: "Requests Used",
    train_position: "Current Train Position",
    group_members_title: "Co-Travelers in your Booking",

    // Matching & Exchange
    match_title: "Eligible Exchange Candidates",
    match_subtitle: "Ranked co-passengers with overlapping journey segments",
    best_match: "Best Match",
    possible_match: "Possible Match",
    btn_request_swap: "Request Exchange",
    why_label: "Why this match:",
    distance_label: "Distance:",
    stops_away: "stops gap",
    confirm_modal_title: "Confirm Seat Exchange Request",
    confirm_modal_body: "Are you sure you want to request an exchange for this berth?",
    expiry_notice: "Notice: Reminders support compliance but cannot physically enforce returning to original berths.",
    btn_confirm: "Send Request",
    btn_cancel: "Cancel",

    // Requests Status
    status_pending: "Awaiting Co-passenger Consent",
    status_accepted: "Accepted by Passenger (Awaiting TTE)",
    status_declined: "Declined",
    status_cancelled: "Cancelled",
    status_approved: "Active & Approved by TTE",
    status_rejected: "Rejected by TTE",
    status_clarification: "Clarification Needed",
    status_expired: "Expired (Returned to Original Berth)",

    // Incoming & Actions
    incoming_empty: "No pending requests from other passengers at this time.",
    btn_accept: "Accept Exchange",
    btn_decline: "Decline",

    // Family Group
    group_title: "Family Group Seating",
    group_subtitle: "Coordinate multi-member seat exchanges collectively",
    btn_submit_group: "Submit Linked Requests",
    group_status_pending: "Pending All Consents",
    group_status_partial: "Partially Confirmed",
    group_status_full: "Fully Confirmed",
    group_status_failed: "Failed (Member Declined / Ineligible)",

    // TTE & Slips
    tte_badge: "TTE Verified",
    btn_view_slip: "View Digital Slip & QR",
    slip_title: "Official Seat Exchange Slip",
    slip_disclaimer: "RailMitra record – not an official Indian Railways document.",

    // Footer Disclaimer
    footer_disclaimer: "Prototype using a simulated reservation dataset. Not the official Indian Railways reservation chart or database. Official use would require authorization from Indian Railways."
  },

  hi: {
    app_title: "रेल मित्र",
    app_subtitle: "स्मार्ट रेलवे सीट विनिमय और पारिवारिक सीटिंग प्रणाली",
    prototype_badge: "प्रोटोटाइप",
    demo_mode_banner: "डेमो मोड सक्रिय: सिम्युलेटेड आरक्षण डेटा। ओटीपी नीचे प्रदर्शित है।",
    
    // Auth & Login
    login_title: "यात्री लॉगिन",
    login_subtitle: "सीट विनिमय अनुरोध करने के लिए अपने यात्रा विवरण दर्ज करें",
    pnr_label: "१०-अंकीय पीएनआर",
    pnr_placeholder: "उदा. PNR1000001",
    train_label: "ट्रेन नंबर",
    train_placeholder: "उदा. 12951",
    date_label: "यात्रा की तिथि",
    date_placeholder: "YYYY-MM-DD",
    btn_validate: "यात्रा सत्यापित करें",
    otp_title: "ओटीपी सत्यापन",
    otp_subtitle: "अपने सिम्युलेटेड नंबर पर प्राप्त ६-अंकीय कोड दर्ज करें",
    otp_label: "सत्यापन कोड (ओटीपी)",
    otp_placeholder: "६-अंकीय ओटीपी",
    btn_verify: "सत्यापित करें और प्रवेश करें",
    btn_resend_otp: "पुनः कोड भेजें",
    btn_logout: "लॉगआउट",
    lockout_warning: "३ असफल प्रयासों के कारण खाता अस्थायी रूप से लॉक है। प्रतीक्षा करें:",
    seconds: "सेकंड",

    // Navigation & Tabs
    tab_home: "यात्रा विवरण",
    tab_find_matches: "सीट विनिमय खोजें",
    tab_my_requests: "मेरे अनुरोध",
    tab_incoming: "आने वाले अनुरोध",
    tab_group_request: "पारिवारिक समूह",
    tab_notifications: "सूचनाएं",

    // Journey Home
    journey_summary: "आपकी यात्रा का सारांश",
    passenger: "यात्री",
    berth_assigned: "वर्तमान बर्थ",
    route_segment: "आपका मार्ग",
    quota_badge: "प्रयुक्त अनुरोध",
    train_position: "ट्रेन की वर्तमान स्थिति",
    group_members_title: "आपकी बुकिंग में सह-यात्री",

    // Matching & Exchange
    match_title: "उपयुक्त विनिमय उम्मीदवार",
    match_subtitle: "समान यात्रा खंड वाले सह-यात्री",
    best_match: "सर्वश्रेष्ठ विकल्प",
    possible_match: "संभावित विकल्प",
    btn_request_swap: "विनिमय का अनुरोध करें",
    why_label: "यह विकल्प क्यों:",
    distance_label: "दूरी:",
    stops_away: "स्टॉप दूर",
    confirm_modal_title: "सीट विनिमय अनुरोध की पुष्टि करें",
    confirm_modal_body: "क्या आप इस बर्थ के लिए विनिमय अनुरोध भेजना चाहते हैं?",
    expiry_notice: "सूचना: अनुस्मारक केवल सुविधा के लिए हैं, मूल बर्थ पर लौटने की भौतिक बाध्यता नहीं है।",
    btn_confirm: "अनुरोध भेजें",
    btn_cancel: "रद्द करें",

    // Requests Status
    status_pending: "सह-यात्री की सहमति की प्रतीक्षा",
    status_accepted: "यात्री द्वारा स्वीकृत (टीटीई समीक्षा लंबित)",
    status_declined: "अस्वीकृत",
    status_cancelled: "रद्द किया गया",
    status_approved: "सक्रिय एवं टीटीई द्वारा अनुमोदित",
    status_rejected: "टीटीई द्वारा अस्वीकृत",
    status_clarification: "स्पष्टीकरण आवश्यक",
    status_expired: "समाप्त (मूल बर्थ पर वापस जाएं)",

    // Incoming & Actions
    incoming_empty: "इस समय कोई नया अनुरोध नहीं है।",
    btn_accept: "स्वीकार करें",
    btn_decline: "अस्वीकार करें",

    // Family Group
    group_title: "पारिवारिक समूह सीटिंग",
    group_subtitle: "परिवार के सभी सदस्यों के लिए एक साथ सीट विनिमय करें",
    btn_submit_group: "समूह अनुरोध भेजें",
    group_status_pending: "सभी सहमतियों की प्रतीक्षा",
    group_status_partial: "आंशिक रूप से पुष्ट",
    group_status_full: "पूर्णतः पुष्ट",
    group_status_failed: "विफल (सदस्य ने अस्वीकार किया)",

    // TTE & Slips
    tte_badge: "टीटीई सत्यापित",
    btn_view_slip: "डिजिटल पर्ची और क्यूआर देखें",
    slip_title: "आधिकारिक सीट विनिमय पर्ची",
    slip_disclaimer: "रेल मित्र रिकॉर्ड – यह भारतीय रेलवे का आधिकारिक दस्तावेज नहीं है।",

    // Footer Disclaimer
    footer_disclaimer: "सिम्युलेटेड आरक्षण डेटासेट का उपयोग करने वाला प्रोटोटाइप। आधिकारिक उपयोग के लिए भारतीय रेलवे से अनुमति आवश्यक होगी।"
  },

  kn: {
    app_title: "ರೈಲ್ ಮಿತ್ರ",
    app_subtitle: "ಸ್ಮಾರ್ಟ್ ರೈಲ್ವೆ ಸೀಟು ವಿನಿಮಯ ಮತ್ತು ಕುಟುಂಬ ಸೀಟಿಂಗ್ ವ್ಯವಸ್ಥೆ",
    prototype_badge: "ಮಾದರಿ (ಪ್ರೋಟೋಟೈಪ್)",
    demo_mode_banner: "ಡೆಮೊ ಮೋಡ್ ಸಕ್ರಿಯವಾಗಿದೆ: ಮಾದರಿ ದತ್ತಾಂಶ. ಒಟಿಪಿ ಕೆಳಗೆ ಲಭ್ಯವಿದೆ.",
    
    // Auth & Login
    login_title: "ಪ್ರಯಾಣಿಕರ ಲಾಗಿನ್",
    login_subtitle: "ಸೀಟು ವಿನಿಮಯ ಮಾಡಲು ನಿಮ್ಮ ಪ್ರಯಾಣದ ವಿವರಗಳನ್ನು ನಮೂದಿಸಿ",
    pnr_label: "೧೦-ಅಂಕಿಯ ಪಿಎನ್‌ಆರ್",
    pnr_placeholder: "ಉದಾ. PNR1000001",
    train_label: "ರೈಲು ಸಂಖ್ಯೆ",
    train_placeholder: "ಉದಾ. 12951",
    date_label: "ಪ್ರಯಾಣದ ದಿನಾಂಕ",
    date_placeholder: "YYYY-MM-DD",
    btn_validate: "ಪ್ರಯಾಣ ಪರಿಶೀಲಿಸಿ",
    otp_title: "ಒಟಿಪಿ ಪರಿಶೀಲನೆ",
    otp_subtitle: "ನಿಮ್ಮ ಮಾದರಿ ಸಂಖ್ಯೆಗೆ ಕಳುಹಿಸಲಾದ ೬-ಅಂಕಿಯ ಕೋಡ್ ನಮೂದಿಸಿ",
    otp_label: "ಪರಿಶೀಲನಾ ಕೋಡ್ (ಒಟಿಪಿ)",
    otp_placeholder: "೬-ಅಂಕಿಯ ಒಟಿಪಿ",
    btn_verify: "ಪರಿಶೀಲಿಸಿ & ಪ್ರವೇಶಿಸಿ",
    btn_resend_otp: "ಮತ್ತೊಮ್ಮೆ ಕಳುಹಿಸಿ",
    btn_logout: "ಸೈನ್ ಔಟ್",
    lockout_warning: "ಖಾತೆ ತಾತ್ಕಾಲಿಕವಾಗಿ ಲಾಕ್ ಆಗಿದೆ. ದಯವಿಟ್ಟು ಕಾಯಿರಿ:",
    seconds: "ಸೆಕೆಂಡುಗಳು",

    // Navigation & Tabs
    tab_home: "ಪ್ರಯಾಣದ ವಿವರ",
    tab_find_matches: "ಸೀಟು ವಿನಿಮಯ ಹುಡುಕಿ",
    tab_my_requests: "ನನ್ನ ವಿನಂತಿಗಳು",
    tab_incoming: "ಬಂದ ವಿನಂತಿಗಳು",
    tab_group_request: "ಕುಟುಂಬದ ಗುಂಪು",
    tab_notifications: "ಸೂಚನೆಗಳು",

    // Journey Home
    journey_summary: "ನಿಮ್ಮ ಪ್ರಯಾಣದ ವಿವರಗಳು",
    passenger: "ಪ್ರಯಾಣಿಕ",
    berth_assigned: "ಹಾಲಿ ಬರ್ತ್",
    route_segment: "ನಿಮ್ಮ ಮಾರ್ಗ",
    quota_badge: "ಬಳಸಿದ ವಿನಂತಿಗಳು",
    train_position: "ರೈಲಿನ ಪ್ರಸ್ತುತ ಸ್ಥಾನ",
    group_members_title: "ಜೊತೆ ಪ್ರಯಾಣಿಕರು",

    // Matching & Exchange
    match_title: "ಲಭ್ಯವಿರುವ ವಿನಿಮಯ ಅಭ್ಯರ್ಥಿಗಳು",
    match_subtitle: "ಹೊಂದಾಣಿಕೆಯಾಗುವ ಸಹ-ಪ್ರಯಾಣಿಕರು",
    best_match: "ಉತ್ತಮ ಹೊಂದಾಣಿಕೆ",
    possible_match: "ಸಂಭಾವ್ಯ ಹೊಂದಾಣಿಕೆ",
    btn_request_swap: "ವಿನಿಮಯಕ್ಕೆ ವಿನಂತಿಸಿ",
    why_label: "ಕಾರಣ:",
    distance_label: "ದೂರ:",
    stops_away: "ನಿಲ್ದಾಣಗಳ ಅಂತರ",
    confirm_modal_title: "ಸೀಟು ವಿನಿಮಯ ಖಚಿತಪಡಿಸಿ",
    confirm_modal_body: "ನೀವು ಈ ಬರ್ತ್‌ಗಾಗಿ ವಿನಿಮಯ ವಿನಂತಿಯನ್ನು ಕಳುಹಿಸಲು ಬಯಸುವಿರಾ?",
    expiry_notice: "ಸೂಚನೆ: ಮೂಲ ಬರ್ತ್‌ಗೆ ಮರಳಲು ಜ್ಞಾಪನೆಗಳು ಸಹಾಯಕವಾಗಿವೆ, ಕಡ್ಡಾಯವಲ್ಲ.",
    btn_confirm: "ವಿನಂತಿ ಕಳುಹಿಸಿ",
    btn_cancel: "ರದ್ದುಮಾಡಿ",

    // Requests Status
    status_pending: "ಸಹ-ಪ್ರಯಾಣಿಕರ ಒಪ್ಪಿಗೆ ಬಾಕಿ ಇದೆ",
    status_accepted: "ಪ್ರಯಾಣಿಕರಿಂದ ಅಂಗೀಕೃತ (ಟಿಟಿಇ ಅನುಮೋದನೆ ಬಾಕಿ)",
    status_declined: "ತಿರಸ್ಕರಿಸಲಾಗಿದೆ",
    status_cancelled: "ರದ್ದುಗೊಳಿಸಲಾಗಿದೆ",
    status_approved: "ಸಕ್ರಿಯ ಮತ್ತು ಟಿಟಿಇ ಅನುಮೋದಿತ",
    status_rejected: "ಟಿಟಿಇ ತಿರಸ್ಕರಿಸಿದೆ",
    status_clarification: "ಸ್ಪಷ್ಟನೆ ಅಗತ್ಯವಿದೆ",
    status_expired: "ಅವಧಿ ಮುಗಿದಿದೆ (ಮೂಲ ಬರ್ತ್‌ಗೆ ಮರಳಿ)",

    // Incoming & Actions
    incoming_empty: "ಯಾವುದೇ ಹೊಸ ವಿನಂತಿಗಳಿಲ್ಲ.",
    btn_accept: "ಸ್ವೀಕರಿಸಿ",
    btn_decline: "ತಿರಸ್ಕರಿಸಿ",

    // Family Group
    group_title: "ಕುಟುಂಬ ಗುಂಪು ಸೀಟಿಂಗ್",
    group_subtitle: "ಕುಟುಂಬ ಸದಸ್ಯರೆಲ್ಲರ ಸೀಟುಗಳನ್ನು ಒಟ್ಟಿಗೆ ಬದಲಾಯಿಸಿ",
    btn_submit_group: "ಗುಂಪು ವಿನಂತಿ ಕಳುಹಿಸಿ",
    group_status_pending: "ಎಲ್ಲಾ ಒಪ್ಪಿಗೆಗಳಿಗಾಗಿ ಕಾಯಲಾಗುತ್ತಿದೆ",
    group_status_partial: "ಭಾಗಶಃ ದೃಢಪಟ್ಟಿದೆ",
    group_status_full: "ಸಂಪೂರ್ಣವಾಗಿ ದೃಢಪಟ್ಟಿದೆ",
    group_status_failed: "ವಿಫಲವಾಗಿದೆ",

    // TTE & Slips
    tte_badge: "ಟಿಟಿಇ ಪರಿಶೀಲಿತ",
    btn_view_slip: "ಡಿಜಿಟಲ್ ರಶೀದಿ ಮತ್ತು ಕ್ಯೂಆರ್ ಕೋಡ್",
    slip_title: "ಅಧಿಕೃತ ಸೀಟು ವಿನಿಮಯ ರಶೀದಿ",
    slip_disclaimer: "ರೈಲ್ ಮಿತ್ರ ದಾಖಲೆ – ಇದು ಭಾರತೀಯ ರೈಲ್ವೆಯ ಅಧಿಕೃತ ದಾಖಲೆಯಲ್ಲ.",

    // Footer Disclaimer
    footer_disclaimer: "ಸಿಮ್ಯುಲೇಟೆಡ್ ರಿಸರ್ವೇಶನ್ ಡೇಟಾಸೆಟ್ ಬಳಸುತ್ತಿರುವ ಮಾದರಿ. ಅಧಿಕೃತ ಬಳಕೆಗೆ ಭಾರತೀಯ ರೈಲ್ವೆಯ ಅನುಮತಿ ಅಗತ್ಯ."
  }
};

let currentLang = localStorage.getItem('rm_lang') || 'en';

function t(key) {
  const dict = translations[currentLang] || translations.en;
  return dict[key] || translations.en[key] || key;
}

function setLanguage(lang) {
  if (translations[lang]) {
    currentLang = lang;
    localStorage.setItem('rm_lang', lang);
    applyTranslations();
  }
}

function getLanguage() {
  return currentLang;
}

function applyTranslations() {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    const translation = t(key);
    if (el.tagName === 'INPUT' && (el.type === 'text' || el.type === 'password' || el.type === 'search')) {
      el.placeholder = translation;
    } else {
      el.textContent = translation;
    }
  });

  // Update html lang attribute
  document.documentElement.lang = currentLang;

  // Dispatch custom event for dynamic components to update
  window.dispatchEvent(new CustomEvent('languageChanged', { detail: { lang: currentLang } }));
}

// Initialise on DOM load
document.addEventListener('DOMContentLoaded', () => {
  applyTranslations();
});

window.i18n = {
  t,
  setLanguage,
  getLanguage,
  applyTranslations
};
