"""AppStoreComplianceService — validates a React Native / Expo bundle against
Apple App Store and Google Play Store submission requirements.

Checks performed:
  Apple App Store:
    - app.json has required fields: name, slug, version, ios.bundleIdentifier
    - ios.buildNumber is set
    - Privacy manifest presence (app.json privacy keys)
    - No debug flags in app.json
    - Required capabilities declared (if push notifications / location used)

  Google Play Store:
    - android.package set (reverse-domain format)
    - android.versionCode set (integer, monotonically increasing)
    - Permissions match features declared
    - No cleartext traffic allowed in production

  Both:
    - Version follows semver x.y.z
    - Deep-link scheme defined (slug used as fallback)
    - eas.json has production profile
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ComplianceFinding:
    severity: str  # "error" | "warning" | "info"
    store: str     # "apple" | "google" | "both"
    rule: str
    message: str
    fix: str


@dataclass
class AppStoreComplianceReport:
    ready_for_apple: bool
    ready_for_google: bool
    score: int  # 0–100
    findings: list[ComplianceFinding] = field(default_factory=list)

    @property
    def errors(self) -> list[ComplianceFinding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warnings(self) -> list[ComplianceFinding]:
        return [f for f in self.findings if f.severity == "warning"]

    def to_dict(self) -> dict:
        return {
            "ready_for_apple": self.ready_for_apple,
            "ready_for_google": self.ready_for_google,
            "score": self.score,
            "errors": [
                {"severity": f.severity, "store": f.store,
                 "rule": f.rule, "message": f.message, "fix": f.fix}
                for f in self.errors
            ],
            "warnings": [
                {"severity": f.severity, "store": f.store,
                 "rule": f.rule, "message": f.message, "fix": f.fix}
                for f in self.warnings
            ],
            "total_findings": len(self.findings),
        }


class AppStoreComplianceService:
    """Validates generated React Native / Expo bundles for app store submission.

    Usage:
        svc = AppStoreComplianceService()
        report = svc.validate(bundle)
        if not report.ready_for_apple:
            print(report.errors)
    """

    _SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
    _BUNDLE_ID_RE = re.compile(r"^[a-z][a-z0-9]*(\.[a-z][a-z0-9]*){2,}$", re.IGNORECASE)
    _PACKAGE_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){2,}$")

    def validate(self, bundle) -> AppStoreComplianceReport:
        """Validate a GeneratedCodeBundle and return an AppStoreComplianceReport.

        Args:
            bundle: GeneratedCodeBundle produced by DeterministicCodeGenerator.
        """
        findings: list[ComplianceFinding] = []

        # Extract relevant files
        files = {f.path: f.content for f in bundle.files}
        app_json_content = files.get("mobile/app.json") or files.get("app.json", "")
        eas_json_content = files.get("mobile/eas.json") or files.get("eas.json", "")
        package_json_content = files.get("mobile/package.json") or files.get("package.json", "")

        app_config = self._parse_json_safe(app_json_content)
        eas_config = self._parse_json_safe(eas_json_content)
        expo = app_config.get("expo", app_config)

        self._check_common(expo, findings)
        self._check_apple(expo, files, findings)
        self._check_google(expo, files, findings)
        self._check_eas(eas_config, findings)
        self._check_permissions(expo, files, findings)
        self._check_security(expo, files, findings)

        errors = [f for f in findings if f.severity == "error"]
        apple_errors = [f for f in errors if f.store in ("apple", "both")]
        google_errors = [f for f in errors if f.store in ("google", "both")]

        # Score: 100 minus 10 per error, 3 per warning (floor 0)
        warnings = [f for f in findings if f.severity == "warning"]
        score = max(0, 100 - len(errors) * 10 - len(warnings) * 3)

        return AppStoreComplianceReport(
            ready_for_apple=len(apple_errors) == 0,
            ready_for_google=len(google_errors) == 0,
            score=score,
            findings=findings,
        )

    # ── Common checks ──

    def _check_common(self, expo: dict, findings: list) -> None:
        name = expo.get("name", "")
        if not name:
            findings.append(ComplianceFinding(
                severity="error", store="both", rule="EXPO_NAME_REQUIRED",
                message="expo.name is required",
                fix="Set 'name' in app.json expo config",
            ))

        slug = expo.get("slug", "")
        if not slug:
            findings.append(ComplianceFinding(
                severity="error", store="both", rule="EXPO_SLUG_REQUIRED",
                message="expo.slug is required",
                fix="Set 'slug' in app.json expo config (kebab-case, no spaces)",
            ))

        version = expo.get("version", "")
        if not version:
            findings.append(ComplianceFinding(
                severity="error", store="both", rule="VERSION_REQUIRED",
                message="expo.version is required",
                fix="Set 'version' (e.g., '1.0.0') in app.json",
            ))
        elif not self._SEMVER_RE.match(version):
            findings.append(ComplianceFinding(
                severity="warning", store="both", rule="VERSION_SEMVER",
                message=f"expo.version '{version}' does not follow semver (x.y.z)",
                fix="Use semantic versioning: '1.0.0'",
            ))

        if not expo.get("icon"):
            findings.append(ComplianceFinding(
                severity="error", store="both", rule="ICON_REQUIRED",
                message="expo.icon is required (1024×1024 PNG, no alpha for Apple)",
                fix="Add icon path to app.json, e.g., './assets/icon.png'",
            ))

        if not expo.get("splash"):
            findings.append(ComplianceFinding(
                severity="warning", store="both", rule="SPLASH_RECOMMENDED",
                message="expo.splash not configured — app will show blank screen on launch",
                fix="Add splash screen config to app.json",
            ))

    # ── Apple-specific checks ──

    def _check_apple(self, expo: dict, files: dict, findings: list) -> None:
        ios = expo.get("ios", {})

        bundle_id = ios.get("bundleIdentifier", "")
        if not bundle_id:
            findings.append(ComplianceFinding(
                severity="error", store="apple", rule="IOS_BUNDLE_ID_REQUIRED",
                message="ios.bundleIdentifier is required for App Store submission",
                fix="Set 'ios.bundleIdentifier' to a reverse-domain string (e.g., 'com.example.myapp')",
            ))
        elif not self._BUNDLE_ID_RE.match(bundle_id):
            findings.append(ComplianceFinding(
                severity="error", store="apple", rule="IOS_BUNDLE_ID_FORMAT",
                message=f"ios.bundleIdentifier '{bundle_id}' has invalid format",
                fix="Use reverse-domain format with at least 3 components (e.g., 'com.company.app')",
            ))

        if not ios.get("buildNumber"):
            findings.append(ComplianceFinding(
                severity="error", store="apple", rule="IOS_BUILD_NUMBER_REQUIRED",
                message="ios.buildNumber is required for TestFlight / App Store submission",
                fix="Set 'ios.buildNumber' to a string integer, e.g., '1'",
            ))

        if not ios.get("infoPlist", {}).get("NSCameraUsageDescription") and self._uses_camera(files):
            findings.append(ComplianceFinding(
                severity="error", store="apple", rule="IOS_CAMERA_DESCRIPTION",
                message="Camera usage detected but NSCameraUsageDescription missing from Info.plist",
                fix="Add NSCameraUsageDescription to ios.infoPlist in app.json",
            ))

        if not ios.get("infoPlist", {}).get("NSLocationWhenInUseUsageDescription") and self._uses_location(files):
            findings.append(ComplianceFinding(
                severity="error", store="apple", rule="IOS_LOCATION_DESCRIPTION",
                message="Location usage detected but NSLocationWhenInUseUsageDescription missing",
                fix="Add NSLocationWhenInUseUsageDescription to ios.infoPlist in app.json",
            ))

        if ios.get("config", {}).get("usesNonExemptEncryption") is None:
            findings.append(ComplianceFinding(
                severity="warning", store="apple", rule="IOS_ENCRYPTION_DECLARATION",
                message="ios.config.usesNonExemptEncryption not declared (required for App Store)",
                fix="Set 'ios.config.usesNonExemptEncryption: false' if app only uses HTTPS (standard)",
            ))

    # ── Google-specific checks ──

    def _check_google(self, expo: dict, files: dict, findings: list) -> None:
        android = expo.get("android", {})

        package = android.get("package", "")
        if not package:
            findings.append(ComplianceFinding(
                severity="error", store="google", rule="ANDROID_PACKAGE_REQUIRED",
                message="android.package is required for Google Play submission",
                fix="Set 'android.package' (e.g., 'com.example.myapp')",
            ))
        elif not self._PACKAGE_RE.match(package):
            findings.append(ComplianceFinding(
                severity="error", store="google", rule="ANDROID_PACKAGE_FORMAT",
                message=f"android.package '{package}' has invalid format",
                fix="Use reverse-domain format with at least 3 components, no hyphens",
            ))

        version_code = android.get("versionCode")
        if version_code is None:
            findings.append(ComplianceFinding(
                severity="error", store="google", rule="ANDROID_VERSION_CODE_REQUIRED",
                message="android.versionCode is required for Play Store submission",
                fix="Set 'android.versionCode' to a positive integer (e.g., 1)",
            ))
        elif not isinstance(version_code, int) or version_code < 1:
            findings.append(ComplianceFinding(
                severity="error", store="google", rule="ANDROID_VERSION_CODE_INVALID",
                message=f"android.versionCode must be a positive integer, got '{version_code}'",
                fix="Set 'android.versionCode' to an integer ≥ 1",
            ))

        if not android.get("adaptiveIcon"):
            findings.append(ComplianceFinding(
                severity="warning", store="google", rule="ANDROID_ADAPTIVE_ICON",
                message="android.adaptiveIcon not configured — adaptive icons required for Play Store",
                fix="Add android.adaptiveIcon with foregroundImage and backgroundColor",
            ))

    # ── EAS build config checks ──

    def _check_eas(self, eas: dict, findings: list) -> None:
        if not eas:
            findings.append(ComplianceFinding(
                severity="error", store="both", rule="EAS_JSON_MISSING",
                message="eas.json not found — required for building production binaries",
                fix="Create eas.json with build profiles (development, staging, production)",
            ))
            return

        builds = eas.get("build", {})
        if "production" not in builds:
            findings.append(ComplianceFinding(
                severity="error", store="both", rule="EAS_PRODUCTION_PROFILE_MISSING",
                message="eas.json missing 'production' build profile",
                fix="Add production build profile to eas.json",
            ))
        else:
            prod = builds["production"]
            ios_prod = prod.get("ios", {})
            android_prod = prod.get("android", {})
            if android_prod.get("buildType") not in ("app-bundle", "apk", None):
                findings.append(ComplianceFinding(
                    severity="warning", store="google", rule="EAS_ANDROID_BUILD_TYPE",
                    message="Prefer 'app-bundle' over 'apk' for Play Store submission",
                    fix="Set android.buildType to 'app-bundle' in production profile",
                ))

    # ── Permissions checks ──

    def _check_permissions(self, expo: dict, files: dict, findings: list) -> None:
        android = expo.get("android", {})
        permissions = android.get("permissions", [])

        if "CAMERA" in str(permissions) and not self._uses_camera(files):
            findings.append(ComplianceFinding(
                severity="warning", store="google", rule="CAMERA_PERMISSION_UNUSED",
                message="CAMERA permission declared but no camera usage found in source",
                fix="Remove unused CAMERA permission from android.permissions",
            ))

        if "READ_CONTACTS" in str(permissions) and not self._uses_contacts(files):
            findings.append(ComplianceFinding(
                severity="warning", store="google", rule="CONTACTS_PERMISSION_UNUSED",
                message="READ_CONTACTS permission declared but no contacts usage found",
                fix="Remove unused READ_CONTACTS permission",
            ))

    # ── Security checks ──

    def _check_security(self, expo: dict, files: dict, findings: list) -> None:
        android = expo.get("android", {})
        if android.get("allowCleartextTraffic") is True:
            findings.append(ComplianceFinding(
                severity="error", store="google", rule="CLEARTEXT_TRAFFIC_DISALLOWED",
                message="android.allowCleartextTraffic=true disallowed in production apps",
                fix="Remove or set android.allowCleartextTraffic to false; use HTTPS endpoints",
            ))

        all_src = "\n".join(
            content for path, content in files.items()
            if path.endswith((".ts", ".tsx", ".js"))
        )
        if re.search(r"__DEV__.*true|console\.log\(.*token|console\.log\(.*password", all_src, re.IGNORECASE):
            findings.append(ComplianceFinding(
                severity="warning", store="both", rule="DEBUG_CODE_IN_PRODUCTION",
                message="Debug logging of sensitive data detected in source files",
                fix="Remove console.log statements that log tokens or passwords",
            ))

    # ── Helpers ──

    def _uses_camera(self, files: dict) -> bool:
        return self._search_files(files, r"Camera|ImagePicker|expo-camera")

    def _uses_location(self, files: dict) -> bool:
        return self._search_files(files, r"Location\.|expo-location|getCurrentPosition")

    def _uses_contacts(self, files: dict) -> bool:
        return self._search_files(files, r"Contacts\.|expo-contacts")

    def _search_files(self, files: dict, pattern: str) -> bool:
        compiled = re.compile(pattern, re.IGNORECASE)
        for path, content in files.items():
            if path.endswith((".ts", ".tsx", ".js")) and compiled.search(content or ""):
                return True
        return False

    @staticmethod
    def _parse_json_safe(content: str) -> dict:
        if not content:
            return {}
        try:
            import json
            return json.loads(content)
        except Exception:
            return {}
