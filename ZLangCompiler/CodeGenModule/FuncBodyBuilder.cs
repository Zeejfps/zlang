using LLVMSharp.Interop;
using ParserModule;
using ParserModule.Nodes;

namespace CodeGenModule;

internal sealed class FuncBodyBuilder : IAstNodeVisitor
{
    private readonly LLVMValueRef _funcRef;
    private readonly LLVMBuilderRef _builder;
    
    public FuncBodyBuilder(LLVMValueRef funcRef)
    {
        _funcRef = funcRef;
        _builder = LLVMBuilderRef.Create(LLVMContextRef.Global);
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
        throw new NotImplementedException();
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
        Console.WriteLine("VisitBlockStatement");
        var block = _funcRef.AppendBasicBlock("entry");
        _builder.PositionAtEnd(block);
        foreach (var statement in node.Statements)
        {
            statement.Accept(this);
        }
    }

    public void VisitFunctionDeclarationNode(FunctionDeclarationNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitReturnStatementNode(ReturnStatementNode node)
    {
        Console.WriteLine("VisitReturnStatementNode");
        if (node.Value == null)
        {
            Console.WriteLine("Returning void");
            _builder.BuildRetVoid();
            return;
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
}