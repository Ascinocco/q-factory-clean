# Local iOS builds, Simulator tests and paired iPhone delivery

Use this procedure for a managed native iOS project. Start with `factory.md`
and the project's `AGENTS.md`, `CLAUDE.md` and technical guide. The project owns
its scheme, bundle ID, dependencies, tests and product acceptance; this runbook
owns the reusable Apple tooling workflow. It is a procedure, not a deployment
service. Apply the current user's authorization before installing on a device.

## What wireless delivery means

Build a signed development `.app` on the Mac, then use Xcode's paired-device
connection to install it with `devicectl`. The same commands work through USB or
a reachable paired network connection. This is not TestFlight, an App Store
release, an app self-update mechanism, or delivery to arbitrary phones over the
internet. It does not use the app's SSH/Tailscale connection. A successful
`tunnel connection` message alone does not establish which physical transport
was used; only claim cable-free delivery after testing with the cable removed.

Initial pairing needs human interaction: connect/unlock the phone, trust the
Mac, complete Xcode pairing, and enable Developer Mode on the phone if prompted.
Sign into an Apple account in Xcode and select a development team. Use automatic
signing for local builds. A Personal Team can support initial device development;
provisioning is time-limited, so later rebuild/reinstall may be necessary.
Keep signing settings local; do not commit certificates, provisioning profiles,
account identifiers or device IDs. Do not assume an old team/device ID still applies.

With the device paired, put Mac and phone on a reachable local network and keep
the phone awake/unlocked. In Xcode 16.4, inspect Window > Devices and Simulators;
newer Xcode versions may use Device Hub. Use the network-connect option if that
version exposes it. Verify discovery with `devicectl`; if wireless discovery
fails, reconnect USB and resolve pairing/network reachability first.

Apple references: [wireless running](https://help.apple.com/xcode/mac/current/en.lproj/dev3e2f4ee6d.html),
[pairing](https://help.apple.com/xcode/mac/current/en.lproj/devbc48d1bad.html),
[current device setup](https://developer.apple.com/documentation/xcode/running-your-app-on-simulated-or-physical-devices).

## Discover tools and select the exact source

```sh
xcode-select -p
xcodebuild -version
xcrun devicectl list devices
xcrun simctl list devices available
xcodebuild -list -project MyApp.xcodeproj
git status --short
git rev-parse HEAD
```

Use a named isolated worktree. Preserve the user's signing edits in shared
checkouts. Record the source revision; don't call an old cached binary “latest.”
Use a separate DerivedData directory per task/worktree and separate physical
and simulator build directories. A simulator `.app` cannot run on a phone.
If multiple Xcodes are installed, set `DEVELOPER_DIR` for the command/session
rather than changing the entire machine's selected Xcode unnecessarily.
The installed Xcode must support the device, SDK and runtime combination.

## Build, install and launch on a phone

Replace these example values with the project's instructions and locally
selected development team. Run from the project worktree. For an `.xcworkspace`
project, use `-workspace` instead of `-project`.

```sh
IOS_PROJECT='MyApp.xcodeproj'
IOS_SCHEME='MyApp'
IOS_BUNDLE_ID='com.example.myapp'
IOS_TEAM='YOUR_LOCAL_TEAM_ID'
IOS_DEVICE='UUID_FROM_DEVICECTL'
IOS_DEVICE_BUILD='/tmp/myapp-task-device'

xcodebuild -project "$IOS_PROJECT" -scheme "$IOS_SCHEME" \
  -destination 'generic/platform=iOS' \
  -derivedDataPath "$IOS_DEVICE_BUILD" \
  DEVELOPMENT_TEAM="$IOS_TEAM" CODE_SIGN_STYLE=Automatic \
  CODE_SIGN_IDENTITY='Apple Development' -allowProvisioningUpdates build

# Set the actual product filename; it need not equal the scheme name.
IOS_APP="$IOS_DEVICE_BUILD/Build/Products/Debug-iphoneos/MyApp.app"
xcrun devicectl device install app --device "$IOS_DEVICE" "$IOS_APP"
xcrun devicectl device process launch --device "$IOS_DEVICE" "$IOS_BUNDLE_ID"
```

Stop on build failure: never install a leftover `.app`. Check `BUILD SUCCEEDED`,
then the install result, then launch separately. Device discovery identifiers
from `devicectl` are not interchangeable with Xcode run-destination IDs; the
`generic/platform=iOS` build avoids that mismatch. Use `xcodebuild
-showdestinations` when a real Xcode test destination is needed.

An in-place update with the same bundle/signing identity normally retains the
app sandbox and Keychain access. Never uninstall to “refresh” a build without
considering saved drafts, keys and settings. Do not change the bundle ID/team as
an incidental signing workaround. Installation can succeed while launch fails
because the phone is locked: report that distinction and have the user unlock
and open the installed app. Report install success only from the tool result.

## Simulator lifecycle and automated UI interaction

Select an installed simulator UUID; never hard-code another developer's UUID.
Boot only if it is currently shut down. These commands target Xcode's Simulator,
not the physical phone.

```sh
IOS_SIMULATOR='UUID_FROM_SIMCTL'
IOS_SIM_BUILD='/tmp/myapp-task-simulator'
xcrun simctl boot "$IOS_SIMULATOR"
xcrun simctl bootstatus "$IOS_SIMULATOR" -b
open -a Simulator

xcodebuild -project "$IOS_PROJECT" -scheme "$IOS_SCHEME" \
  -destination "platform=iOS Simulator,id=$IOS_SIMULATOR" \
  -derivedDataPath "$IOS_SIM_BUILD" \
  CODE_SIGN_IDENTITY=- CODE_SIGNING_ALLOWED=YES build
xcrun simctl install "$IOS_SIMULATOR" \
  "$IOS_SIM_BUILD/Build/Products/Debug-iphonesimulator/MyApp.app"
xcrun simctl launch "$IOS_SIMULATOR" "$IOS_BUNDLE_ID"

xcodebuild -project "$IOS_PROJECT" -scheme "$IOS_SCHEME" \
  -destination "platform=iOS Simulator,id=$IOS_SIMULATOR" \
  -derivedDataPath "$IOS_SIM_BUILD" \
  CODE_SIGN_IDENTITY=- CODE_SIGNING_ALLOWED=YES \
  -resultBundlePath /tmp/myapp-task-tests.xcresult test
```

Choose a fresh result-bundle path each run. Ad-hoc signing matters for tests that
exercise Keychain; `CODE_SIGNING_ALLOWED=NO` is useful for compile-only checks,
not a substitute for those tests. Inspect passed/failed/skipped results: a skipped
integration test is not evidence of working transport. Add `-only-testing:` when
narrow verification is appropriate; use the project's actual target/test names.

XCUITest can launch, tap, type, inspect accessibility elements, and verify
relaunch flows through committed tests. `simctl` handles boot/install/launch and
can capture screenshots; it is not a general tap/type automation interface.
A host-provided interactive Simulator tool is a separate optional capability.
Check whether it exists and is enabled; do not claim to have used it or bypass
its disabled setting. Chadmux was validated with XCUITest and CLI tooling when
direct agent UI control was unavailable. No Maestro dependency was required.

For a deliberately synthetic test screen, a local screenshot can aid inspection:

```sh
xcrun simctl io "$IOS_SIMULATOR" screenshot /tmp/myapp-test-screen.png
```

Do not capture personal terminal panes, tokens or user documents. Keep logs and
`.xcresult` artifacts local; publish only sanitized summaries. Do not erase
simulators, reset permissions or delete app data as a routine repair.

## Validation and troubleshooting

| Symptom | Next check |
| --- | --- |
| Pairing never completes | Unlock phone, inspect Trust/Developer Mode prompts and Xcode device status; reconnect USB. |
| Paired but unavailable wirelessly | Wake/unlock phone; verify local network reachability; try USB before changing pairing. |
| No signing profile/certificate | Confirm local Xcode account/team and bundle ID; read the specific signing error. |
| Install succeeds, launch says Locked | Ask user to unlock/open; don't rebuild or uninstall unnecessarily. |
| Simulator Keychain failures | Verify ad-hoc signed tests and correct task DerivedData. |
| Wrong/stale app behavior | Verify worktree revision, build outcome, product path, device and bundle ID. |
| Microphone/camera or mobile networking issue | Reproduce on real hardware with user action; simulator success isn't proof. |

Record source SHA, toolchain, build/test outcome, intended device class, install
and launch results separately. Retain known-good source/build evidence for
recovery; rollback also needs compatible signing and consideration of data
migrations. Real hardware checks cover microphone/camera, permissions, suspension,
network loss and latency. Simulator tests cover reproducible UI/state flows.
TestFlight distribution remains a separate project milestone.

## Project adapters

- [Chadmux local iOS delivery](https://github.com/Ascinocco/chadmux-clean/blob/main/docs/ios-development.md)
  supplies its project names and transport/pilot checks. If a cross-repository
  documentation PR has not merged yet, use its reviewed branch version rather
  than assuming the main-branch link already exists.
