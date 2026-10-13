# Burn Helper installer for Windows. One line, in PowerShell:
#
#   irm https://raw.githubusercontent.com/pureyang/burn-helper/main/install.ps1 | iex
#
# There is one bridge: the computer the badge talks to. That line sets it up on this PC.
# On any other computer, join it to that bridge instead (the bridge install prints this
# line with its address filled in):
#
#   $env:BURN_HELPER_JOIN='http://<bridge>:8787'; irm https://raw.githubusercontent.com/pureyang/burn-helper/main/install.ps1 | iex
#
# With options, either set them first:
#   $env:BURN_HELPER_YES = 1; irm https://raw.githubusercontent.com/pureyang/burn-helper/main/install.ps1 | iex
# or pass them like this:
#   & ([scriptblock]::Create((irm https://raw.githubusercontent.com/pureyang/burn-helper/main/install.ps1))) -Yes
# or from a checkout:
#   powershell -ExecutionPolicy Bypass -File .\install.ps1 -Yes
#
# Options (environment variable in brackets):
#   -Join URL   join the bridge at URL: only hooks and a status line, no badge, no login item [BURN_HELPER_JOIN]
#   -Yes        accept every step without asking (Wi-Fi is then set up from your phone) [BURN_HELPER_YES]
#   -NoFlash    never replace the badge's firmware                                       [BURN_HELPER_NO_FLASH]
#   -NoBadge    only set up this PC                                                       [BURN_HELPER_NO_BADGE]
#   -NoBridge   only set up the badge                                                     [BURN_HELPER_NO_BRIDGE]
#   -DryRun     show what would happen, change nothing                                    [BURN_HELPER_DRY_RUN]
#   -Uninstall  remove the hooks, status line, login item and firewall rule from this PC [BURN_HELPER_UNINSTALL]
#
# What it does: gets the code into ~\burn-helper, installs the bridge (async Claude Code
# hooks, a hearts status line, a login item; settings.json is backed up first), lets the
# badge through Windows Firewall, then backs up and flashes the badge if needed, asks for
# Wi-Fi, and copies the app onto it. Only the firewall rule needs admin approval. At the end
# it shows the line to run on other computers.
param(
  [string]$Join,
  [switch]$Yes,
  [switch]$NoFlash,
  [switch]$NoBadge,
  [switch]$NoBridge,
  [switch]$DryRun,
  [switch]$Uninstall
)

$RuleName = "Burn Helper bridge"
$BridgePort = 8787
# shared by the functions below (a hashtable, so they can change it without scope tricks)
$State = @{ YesAll = $false; PyExe = $null; PyPre = @() }

function Say([string]$msg) {
  Write-Host ([char]0x2665) -ForegroundColor Red -NoNewline
  Write-Host (" " + $msg)
}

function Fail([string]$msg) {
  throw ("BURN_HELPER: " + $msg)
}

function First([object[]]$values) {
  foreach ($v in $values) { if ($v) { return $v } }
  return $null
}

function Flag([bool]$given, [string]$envName) {
  if ($given) { return $true }
  $v = [Environment]::GetEnvironmentVariable($envName)
  return ($v -and $v -ne "0")
}

# a yes/no question; -Yes answers yes to all of them
function Ask([string]$question) {
  if ($State.YesAll) { return $true }
  $answer = Read-Host ($question + " [Y/n]")
  return ($answer -eq "" -or $answer -match '^(y|yes)$')
}

# Python 3: the py launcher first, then python and python3 (skipping the Microsoft Store stub)
function Find-Python {
  foreach ($spec in @("py -3", "python", "python3")) {
    $parts = $spec.Split(" ")
    $exe = $parts[0]
    $pre = @($parts | Select-Object -Skip 1)
    if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
    $out = & $exe @pre -c "import sys; print(sys.version_info[0])" 2>$null
    if ($LASTEXITCODE -eq 0 -and ("" + $out).Trim() -eq "3") {
      $State.PyExe = $exe
      $State.PyPre = $pre
      return $true
    }
  }
  return $false
}

# run Python with a list of arguments (a plain array, so "--dry-run" and the like reach
# Python untouched instead of being read as PowerShell parameters)
function Invoke-Py([string[]]$argv) {
  $all = @($State.PyPre) + @($argv)
  & $State.PyExe @all
}

function Test-FirewallRule {
  return [bool](Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue)
}

# run one PowerShell command as administrator (Windows asks for approval). The caller checks
# the result itself: an elevated process doesn't always report its exit code back.
function Invoke-Elevated([string]$command) {
  $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($command))
  try {
    Start-Process -FilePath "powershell.exe" -Verb RunAs -Wait `
      -ArgumentList ("-NoProfile -ExecutionPolicy Bypass -EncodedCommand " + $encoded) | Out-Null
  } catch {
    # approval declined
  }
}

function Install-BurnHelper {
  $State.YesAll = Flag $Yes.IsPresent "BURN_HELPER_YES"
  $noFlash = Flag $NoFlash.IsPresent "BURN_HELPER_NO_FLASH"
  $noBadge = Flag $NoBadge.IsPresent "BURN_HELPER_NO_BADGE"
  $noBridge = Flag $NoBridge.IsPresent "BURN_HELPER_NO_BRIDGE"
  $dry = Flag $DryRun.IsPresent "BURN_HELPER_DRY_RUN"
  $remove = Flag $Uninstall.IsPresent "BURN_HELPER_UNINSTALL"
  $joinUrl = First @($Join, $env:BURN_HELPER_JOIN)

  $repoUrl = First @($env:BURN_HELPER_REPO, $env:HEARTS_LEFT_REPO, "https://github.com/pureyang/burn-helper.git")
  $ref = First @($env:BURN_HELPER_REF, $env:HEARTS_LEFT_REF, "main")
  $dest = First @($env:BURN_HELPER_DIR, $env:HEARTS_LEFT_DIR, (Join-Path $HOME "burn-helper"))

  $badgeArgs = @()
  if ($State.YesAll) { $badgeArgs += "--yes" }
  if ($noFlash) { $badgeArgs += "--no-flash" }
  if ($dry) { $badgeArgs += "--dry-run" }

  Say "Burn Helper: your Claude Code agents on a Tufty 2350 badge."
  if (-not (Find-Python)) {
    Fail "Python 3 is needed. Install it with: winget install -e --id Python.Python.3.12  (then open a new PowerShell window and run this again)"
  }
  if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Fail "git is needed. It comes with Git for Windows, which Claude Code uses: winget install -e --id Git.Git"
  }

  # 1. the code: this checkout, or a fresh clone in ~\burn-helper
  $root = $null
  if ($PSCommandPath) {
    $here = Split-Path -Parent $PSCommandPath
    if ((Test-Path (Join-Path $here "bridge\install.py")) -and (Test-Path (Join-Path $here "badge"))) { $root = $here }
  }
  if (-not $root) {
    if (Test-Path (Join-Path $dest ".git")) {
      if ($dry) {
        Say "Would update $dest from $repoUrl ($ref)."
      } else {
        Say "Updating $dest ..."
        git -C $dest fetch --quiet origin $ref
        if ($LASTEXITCODE -ne 0) { Fail "Could not fetch updates into $dest." }
        git -C $dest checkout --quiet $ref
        if ($LASTEXITCODE -ne 0) { Fail "Could not check out $ref in $dest." }
        git -C $dest merge --ff-only --quiet ("origin/" + $ref)
        if ($LASTEXITCODE -ne 0) { Fail "$dest has local changes; update it by hand." }
      }
    } elseif (Test-Path $dest) {
      Fail "$dest already exists and is not a Burn Helper checkout. Set BURN_HELPER_DIR to another folder."
    } elseif ($dry) {
      Say "Would clone $repoUrl ($ref) into $dest, then continue."
      return
    } else {
      Say "Downloading Burn Helper into $dest ..."
      git clone --quiet --branch $ref $repoUrl $dest
      if ($LASTEXITCODE -ne 0) { Fail "Could not clone $repoUrl." }
    }
    $root = $dest
  }
  Say "Code: $root"
  $installPy = Join-Path $root "bridge\install.py"

  if ($remove) {
    if ($dry) {
      Invoke-Py @($installPy, "--uninstall", "--dry-run")
      if (Test-FirewallRule) { Say "Would remove the Windows Firewall rule '$RuleName' (asks for admin approval)." }
    } else {
      Invoke-Py @($installPy, "--uninstall")
      if (Test-FirewallRule) {
        Say "Removing the Windows Firewall rule '$RuleName' (Windows asks for approval) ..."
        Invoke-Elevated "Remove-NetFirewallRule -DisplayName '$RuleName'"
        if (-not (Test-FirewallRule)) { Say "Removed the firewall rule." }
        else { Say "The firewall rule is still there; remove '$RuleName' in Windows Defender Firewall if you like." }
      }
    }
    Say "The badge was left as it is. To put its original firmware back:"
    Say "  py $root\scripts\badge.py bootloader, then picotool load -v -x $root\backup\<date>\flash-full.bin"
    return
  }

  if (-not (Test-Path (Join-Path $HOME ".claude"))) {
    Say "Claude Code does not seem to be set up yet (no ~\.claude). Install it, run it once, then rerun this."
  }

  # joining a bridge on another computer: hooks and a status line only
  if ($joinUrl) {
    if ($dry) {
      Invoke-Py @($installPy, "--bridge", $joinUrl, "--dry-run")
    } else {
      Say "This adds async hooks and a hearts status line to ~\.claude\settings.json (backed up first;"
      Say "undo with -Uninstall) that send this PC's Claude Code activity to the bridge."
      if (Ask "Join the bridge at $joinUrl?") {
        Invoke-Py @($installPy, "--bridge", $joinUrl)
        if ($LASTEXITCODE -ne 0) { Fail "Joining did not finish; see the messages above." }
      } else {
        Say "Skipped."
      }
    }
    return
  }

  # the USB cable needs pyserial (Wi-Fi works without it)
  Invoke-Py @("-c", "import serial") 2>$null
  if ($LASTEXITCODE -ne 0) {
    if ($dry) {
      Say "Would install pyserial for the USB cable: py -m pip install --user pyserial"
    } else {
      Say "Installing pyserial, so the bridge and the badge tools can use the USB cable ..."
      Invoke-Py @("-m", "pip", "install", "--user", "--quiet", "--disable-pip-version-check", "pyserial")
      if ($LASTEXITCODE -ne 0) {               # inside a virtual environment --user isn't allowed
        Invoke-Py @("-m", "pip", "install", "--quiet", "--disable-pip-version-check", "pyserial")
      }
      if ($LASTEXITCODE -ne 0) { Say "Could not install pyserial: the USB cable won't work, Wi-Fi still does." }
    }
  }

  # 2. this PC's side: the bridge, and a way through the firewall for the badge
  if (-not $noBridge) {
    Say "This makes this PC the bridge: the one computer the badge talks to. If another computer"
    Say "already is your bridge, stop here (Ctrl+C) and run the join line on this one instead:"
    Say "  `$env:BURN_HELPER_JOIN='http://<bridge>:8787'; irm https://raw.githubusercontent.com/pureyang/burn-helper/main/install.ps1 | iex"
    if ($dry) {
      Invoke-Py @($installPy, "--dry-run")
      if (-not (Test-FirewallRule)) {
        Say "Would add a Windows Firewall rule '$RuleName': inbound TCP $BridgePort on Private networks (asks for admin approval)."
      }
    } else {
      Say "The bridge adds async hooks and a hearts status line to ~\.claude\settings.json"
      Say "(backed up first; undo with -Uninstall) and starts when you sign in."
      if (Ask "Install the bridge on this PC?") {
        Invoke-Py @($installPy)
        if ($LASTEXITCODE -ne 0) { Fail "The bridge install did not finish; see the messages above." }
      } else {
        Say "Skipped the bridge."
      }
      if (Test-FirewallRule) {
        Say "Windows Firewall already lets the badge in (rule '$RuleName')."
      } else {
        Say "Windows Firewall blocks the badge from reaching this PC until a rule allows port $BridgePort."
        if (Ask "Add that rule (inbound TCP $BridgePort, Private networks only; Windows asks for approval)?") {
          $cmd = "New-NetFirewallRule -DisplayName '$RuleName' -Direction Inbound -Protocol TCP " +
                 "-LocalPort $BridgePort -Profile Private -Action Allow | Out-Null"
          Invoke-Elevated $cmd
          if (Test-FirewallRule) { Say "Added the firewall rule." }
          else { Say "No firewall rule added. Over Wi-Fi the badge won't reach this PC; the USB cable still works." }
        } else {
          Say "Skipped the firewall rule. Over Wi-Fi the badge won't reach this PC; the USB cable still works."
        }
      }
      $public = @(Get-NetConnectionProfile -ErrorAction SilentlyContinue | Where-Object { $_.NetworkCategory -eq "Public" })
      if ($public.Count -gt 0) {
        Say ("Your network '" + $public[0].Name + "' is set to Public, where Windows keeps the badge out.")
        Say "Make it Private: Settings > Network & internet > Wi-Fi or Ethernet > your network > Private network."
      }
    }
  }

  # 3. the badge
  if (-not $noBadge) {
    Invoke-Py (@((Join-Path $root "tools\setup_badge.py")) + $badgeArgs)
  }

  $ip = Invoke-Py @("-c", "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(('10.255.255.255', 1)); print(s.getsockname()[0])") 2>$null
  if (-not $ip) { $ip = "<this-pc-ip>" }
  Say ("Done. Phone panel and theme picker: http://" + ("" + $ip).Trim() + ":" + $BridgePort + "/")
  Say "On the badge: A/C change theme, B shows info (twice: Wi-Fi debug), hold B for phone Wi-Fi setup."
  if (-not $noBridge) {
    Write-Host ""
    Invoke-Py @($installPy, "--join-help")
  }
}

try {
  Install-BurnHelper
} catch {
  $msg = "" + $_.Exception.Message
  $heart = [string][char]0x2665
  if ($msg.StartsWith("BURN_HELPER: ")) {
    Write-Host ($heart + " " + $msg.Substring(13)) -ForegroundColor Red
  } else {
    Write-Host ($heart + " Stopped: " + $msg) -ForegroundColor Red
  }
}
