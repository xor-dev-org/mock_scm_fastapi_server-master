Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Read-JsonFile {
    param([string]$Path)
    return Get-Content -Raw -Path $Path | ConvertFrom-Json
}

function Write-JsonFile {
    param(
        [string]$Path,
        [object]$Data,
        [int]$Depth = 30
    )
    $json = $Data | ConvertTo-Json -Depth $Depth
    $json | Out-File -FilePath $Path -Encoding utf8
}

$root = Split-Path -Parent $PSScriptRoot
$poPath = Join-Path $root 'data\purchase_orders.json'
$usersPath = Join-Path $root 'data\users.json'
$suppliersPath = Join-Path $root 'data\suppliers.json'

$purchaseOrders = Read-JsonFile -Path $poPath
foreach ($po in $purchaseOrders) {
    if (-not $po.PSObject.Properties.Name.Contains('po_details')) {
        $po | Add-Member -NotePropertyName po_details -NotePropertyValue @{
            supplier_details = @{
                supplier_no = $po.supplier_id
                email = ''
                address = ''
            }
            buyer_details = @{
                buyer = $po.procurement_specialist_id
                telephone = ''
                email = ''
            }
            shipment_details = @{
                incoterms = ''
                address = ''
            }
            billing_details = @{
                terms_of_payment = $po.payment_terms
                currency = $po.currency
                send_invoice_to = ''
                bill_to_address = ''
            }
        }
    }

    if (-not $po.PSObject.Properties.Name.Contains('status_history')) {
        $po | Add-Member -NotePropertyName status_history -NotePropertyValue @()
    }

    if (-not $po.PSObject.Properties.Name.Contains('workflow_stage')) {
        $po | Add-Member -NotePropertyName workflow_stage -NotePropertyValue 'PO_DETAILS'
    }

    if (-not $po.PSObject.Properties.Name.Contains('last_modified_by')) {
        $po | Add-Member -NotePropertyName last_modified_by -NotePropertyValue ''
    }

    if (-not $po.PSObject.Properties.Name.Contains('last_modified_date')) {
        $po | Add-Member -NotePropertyName last_modified_date -NotePropertyValue ''
    }

    foreach ($line in $po.line_items) {
        $lineNumber = [int]$line.line_number

        if (-not $line.PSObject.Properties.Name.Contains('id')) {
            $line | Add-Member -NotePropertyName id -NotePropertyValue ([string]::Format('{0:D5}', $lineNumber))
        }

        if (-not $line.PSObject.Properties.Name.Contains('unit')) {
            $line | Add-Member -NotePropertyName unit -NotePropertyValue 'EA'
        }

        if (-not $line.PSObject.Properties.Name.Contains('per')) {
            $line | Add-Member -NotePropertyName per -NotePropertyValue 1
        }

        if (-not $line.PSObject.Properties.Name.Contains('supplier_mat_code')) {
            $line | Add-Member -NotePropertyName supplier_mat_code -NotePropertyValue ''
        }

        if (-not $line.PSObject.Properties.Name.Contains('transportation')) {
            $line | Add-Member -NotePropertyName transportation -NotePropertyValue 'PARCEL-GROUND B'
        }

        if (-not $line.PSObject.Properties.Name.Contains('shipment_date')) {
            $line | Add-Member -NotePropertyName shipment_date -NotePropertyValue $po.delivery_date
        }

        if (-not $line.PSObject.Properties.Name.Contains('required_in_house_date')) {
            $line | Add-Member -NotePropertyName required_in_house_date -NotePropertyValue $po.delivery_date
        }

        if (-not $line.PSObject.Properties.Name.Contains('net_value')) {
            $value = [math]::Round(([double]$line.quantity * [double]$line.unit_price), 2)
            $line | Add-Member -NotePropertyName net_value -NotePropertyValue $value
        }

        if (-not $line.PSObject.Properties.Name.Contains('line_status')) {
            $line | Add-Member -NotePropertyName line_status -NotePropertyValue 'ALL'
        }

        if (-not $line.PSObject.Properties.Name.Contains('default_expanded')) {
            $line | Add-Member -NotePropertyName default_expanded -NotePropertyValue $true
        }

        if (-not $line.PSObject.Properties.Name.Contains('documents')) {
            $line | Add-Member -NotePropertyName documents -NotePropertyValue @()
        }

        if (-not $line.PSObject.Properties.Name.Contains('history')) {
            $line | Add-Member -NotePropertyName history -NotePropertyValue @()
        }
    }
}
Write-JsonFile -Path $poPath -Data $purchaseOrders -Depth 30

$users = Read-JsonFile -Path $usersPath
foreach ($user in $users) {
    if (-not $user.PSObject.Properties.Name.Contains('permissions')) {
        if ($user.role -eq 'ADMIN') {
            $user | Add-Member -NotePropertyName permissions -NotePropertyValue @(
                'MOVE_IN',
                'MOVE_OUT',
                'SPLIT',
                'HOLD',
                'REJECT',
                'ACCEPT',
                'NEED_MORE_INFORMATION',
                'MAKE_REVISION',
                'RAISE_CONCESSION',
                'UPLOAD_DOCUMENT'
            )
        }
        elseif ($user.role -eq 'PROCUREMENT_SPECIALIST') {
            $user | Add-Member -NotePropertyName permissions -NotePropertyValue @(
                'MOVE_IN',
                'MOVE_OUT',
                'SPLIT',
                'HOLD',
                'REJECT',
                'ACCEPT',
                'NEED_MORE_INFORMATION'
            )
        }
        else {
            $user | Add-Member -NotePropertyName permissions -NotePropertyValue @()
        }
    }
}
Write-JsonFile -Path $usersPath -Data $users -Depth 12

$suppliers = Read-JsonFile -Path $suppliersPath
foreach ($supplier in $suppliers) {
    if (-not $supplier.PSObject.Properties.Name.Contains('permissions')) {
        $supplier | Add-Member -NotePropertyName permissions -NotePropertyValue @(
            'MAKE_REVISION',
            'RAISE_CONCESSION',
            'UPLOAD_DOCUMENT',
            'ACCEPT'
        )
    }
}
Write-JsonFile -Path $suppliersPath -Data $suppliers -Depth 12

Write-Output 'Seed schema migration completed.'
