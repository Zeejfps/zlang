using LexerModule;
using LLVMSharp.Interop;
using ParserModule;
using ParserModule.Nodes;

namespace CodeGenModule;

internal sealed class StatementVisitor : IAstNodeVisitor
{
    private readonly LLVMBuilderRef _builder;
    private readonly Dictionary<string, LLVMValueRef> _scope;

    public StatementVisitor(LLVMBuilderRef builder, Dictionary<string, LLVMValueRef> scope)
    {
        _builder = builder;
        _scope = scope;
    }
    
    public void VisitLiteralIntegerNode(LiteralIntegerNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitLiteralBoolNode(LiteralBoolNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitBinaryExpression(BinaryExpressionNode node)
    {
        var expressionVisitor = new ExpressionVisitor(_scope);
        
        node.Left.Accept(expressionVisitor);
        var left = expressionVisitor.Value;
        
        node.Right.Accept(expressionVisitor);
        var right = expressionVisitor.Value;
        
        // TODO: Move this into semantic analysis
        if (node.Op.Kind == TokenKind.SymbolPlus)
        {
            var addRef = _builder.BuildAdd(left, right);
            _builder.BuildRet(addRef);
        }
    }

    public void VisitUnaryExpression(UnaryExpressionNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitIdentifierNode(IdentifierNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitVarAssignmentStatement(VarAssignmentStatementNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitNamedTypeNode(NamedTypeNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitBlockStatement(BlockStatementNode node)
    {
        // Console.WriteLine("VisitBlockStatement");
        // var block = _funcRef.AppendBasicBlock("entry");
        // _builder.PositionAtEnd(block);
        // foreach (var statement in node.Statements)
        // {
        //     statement.Accept(this);
        // }
    }

    public void VisitFunctionDeclarationNode(FunctionDefinitionNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitReturnStatementNode(ReturnStatementNode node)
    {
        if (node.Value == null)
        {
            _builder.BuildRetVoid();
        }
        else
        {
            node.Value.Accept(this);
        }
    }

    public void VisitParameterNode(ParameterNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitStructImportNode(StructImportNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitQualifiedIdentifierNode(QualifiedIdentifierNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitStructDefinitionNode(StructDefinitionNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitModuleDefinitionNode(ModuleDefinitionNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitIfStatementNode(IfStatementNode node)
    {
        throw new NotImplementedException();
    }
}