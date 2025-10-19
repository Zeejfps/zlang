using ParserModule.Nodes;
using ParserModule.Visitors;

namespace SemanticAnalysisModule;

public sealed class SymbolsDeclarationAnalyzer : ITopLevelStatementVisitor, IModuleLevelNodeVisitor, IStatementNodeVisitor
{
    private Scope _currentScope = new(null);
    
    public Scope Scope => _currentScope;

    private readonly ExpressionTypeAnalyzer _expressionTypeAnalyzer = new();
    
    public void VisitStructImport(ImportStatementNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitModuleDefinition(ModuleDefinitionNode node)
    {
        _currentScope = new Scope(_currentScope);
        foreach (var statement in node.Body)
        {
            statement.Accept(this);
        }
        _currentScope = _currentScope.Parent!;
    }

    public void VisitFunctionDefinition(FunctionDefinitionNode node)
    {
        var symbol = new Symbol(node.Signature.Identifier, node.Signature.ReturnType, node);
        if (!_currentScope.TryDefine(symbol))
            throw new Exception($"Function '{node.Signature.Identifier}' already defined in this scope.");

        var funcScope = new Scope(_currentScope);
        _currentScope = funcScope;
        
        foreach (var param in node.Signature.Parameters)
        {
            var paramSym = new Symbol(param.Name, param.Type, param);
            if (!_currentScope.TryDefine(paramSym))
                throw new Exception($"Parameter '{param.Name}' already defined.");
        }
        
        node.Body.Accept(this);

        _currentScope = _currentScope.Parent!;
    }

    public void VisitStructDefinition(StructDefinitionNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitExternFunctionDeclaration(ExternFunctionDeclarationNode node)
    {
        var signature = node.Signature;
        var symbol = new Symbol(signature.Identifier, signature.ReturnType, node);
        if (!_currentScope.TryDefine(symbol))
            throw new Exception($"Function '{signature.Identifier}' already defined in this scope.");
    }

    public void VisitIfStatementNode(IfStatementNode node)
    {
        node.ThenBranch.Accept(this);
        node.ElseBranch?.Accept(this);
    }

    public void VisitBlockStatement(BlockStatementNode blockStatement)
    {
        _currentScope = new Scope(_currentScope);
        foreach (var statement in blockStatement.Statements)
        {
            statement.Accept(this);
        }
        _currentScope = _currentScope.Parent!;
    }

    public void VisitReturnStatementNode(ReturnStatementNode node)
    {
    }

    public void VisitForStatement(ForStatemetNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitVarDeclaration(VarDeclarationStatementNode node)
    {
        var specifiedType = node.Type;
        if (specifiedType == null && node.Initializer == null)
            throw new Exception("Variable declaration must have initializer statement or type specified");
        
        if (node.Initializer != null)
        {
            var inferType = _expressionTypeAnalyzer.InferType(node.Initializer);
            if (specifiedType != null && inferType != specifiedType)
                throw new Exception($"Inferred type does not match specified type. Inferred: {inferType}, Specified: {node.Type}");
            
            specifiedType = inferType;
        }
        
        var symbol = new Symbol(node.Identifier, specifiedType, node);
        if (!_currentScope.TryDefine(symbol))
            throw new Exception($"Variable '{node.Identifier}' already defined in this scope.");
    }

    public void VisitVarAssignment(VarAssignmentStatementNode node)
    {
    }

    public void VisitWhileStatement(WhileStatementNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitExpressionStatement(ExpressionStatement node)
    {
        throw new NotImplementedException();
    }

    public void VisitFunctionCall(FunctionCallNode functionCallExpression)
    {
        throw new NotImplementedException();
    }
}