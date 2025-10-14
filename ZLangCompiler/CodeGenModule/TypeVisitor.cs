using LLVMSharp.Interop;
using ParserModule;
using ParserModule.Nodes;

namespace CodeGenModule;

internal sealed class TypeVisitor : IAstNodeVisitor
{
    public LLVMTypeRef Type { get; private set; }
    
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

    public void VisitForStatement(ForStatemetNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitNamedTypeNode(NamedTypeNode node)
    {
        Type = node.Name switch
        {
            "u32" or "i32" => LLVMTypeRef.Int32,
            "u8" or "i8" => LLVMTypeRef.Int8,
            _ => throw new ArgumentOutOfRangeException()
        };
    }

    public void VisitBlockStatement(BlockStatementNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitFunctionDeclarationNode(FunctionDefinitionNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitReturnStatementNode(ReturnStatementNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitParameterNode(ParameterNode node)
    {
        throw new NotImplementedException();
    }

    public void VisitStructImportStatementNode(StructImportStatementNode node)
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