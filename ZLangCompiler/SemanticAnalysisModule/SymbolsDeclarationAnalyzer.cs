using ParserModule.Nodes;
using ParserModule.Nodes.Expressions;
using ParserModule.Visitors;

namespace SemanticAnalysisModule;

public sealed class SymbolsDeclarationAnalyzer : IAstNodeVisitor
{
    
    private Scope _currentScope = new(null);
    
    public void VisitStructImport(ImportStatementNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitModuleDefinition(ModuleDefinitionNode node)
    {
        throw new NotImplementedException();
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
        throw new NotImplementedException();
    }

    public void VisitIfStatementNode(IfStatementNode node)
    {
        throw new NotImplementedException();
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

    public void VisitVarDefinition(VarDefinitionStatementNode node)
    {
        var symbol = new Symbol(node.Identifier, node.Type, node);
        if (!_currentScope.TryDefine(symbol))
            throw new Exception($"Variable '{node.Identifier}' already defined in this scope.");
    }

    public void VisitVarDeclaration(VarDeclarationStatementNode node)
    {
        var symbol = new Symbol(node.Identifier, node.Type, node);
        if (!_currentScope.TryDefine(symbol))
            throw new Exception($"Variable '{node.Identifier}' already defined in this scope.");
    }

    public void VisitVarAssignment(VarAssignmentStatementNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitWhileStatement(WhileStatementNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitExpressionStatement(ExpressionStatement node)
    {
        throw new NotImplementedException();
    }

    public void VisitBinary(BinaryExpressionNode binaryExpression)
    {
        throw new NotImplementedException();
    }

    public void VisitUnary(UnaryExpressionNode unaryExpression)
    {
        throw new NotImplementedException();
    }

    public void VisitLiteralInteger(LiteralIntegerExpressionNode literalIntegerExpression)
    {
        throw new NotImplementedException();
    }

    public void VisitLiteralBool(LiteralBoolExpressionNode literalBoolExpression)
    {
        throw new NotImplementedException();
    }

    public void VisitQualifiedIdentifier(QualifiedIdentifierExpressionNode identifierExpression)
    {
        throw new NotImplementedException();
    }

    public void VisitFunctionCall(FunctionCallNode functionCallExpression)
    {
        throw new NotImplementedException();
    }

    public void VisitNamedType(NamedTypeNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitPtrType(PtrTypeNode node)
    {
        throw new NotImplementedException();
    }
}