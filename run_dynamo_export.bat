@echo off
set DYNAMOEXE="C:\Program Files\Autodesk\Revit 2025\AddIns\DynamoForRevit\DynamoCLI.exe"
set GRAPHFILE="C:\Users\yhuang\Downloads\revit_automation_server\export_levels.dyn"

%DYNAMOEXE% --automation %GRAPHFILE%
